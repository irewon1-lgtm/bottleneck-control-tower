"""Run the exact activated REVIEW transport after formatting-only drift.

Neither activation seals nor old first/history files are migrated or rewritten.
Archived code must have its known hash and the same executable AST as current
code (excluding one known unused datetime import). Any real code change blocks.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import bct
from bct import review_leads as review, review_shadow

COMMIT = 'cae46f42a948a28b9154887cb922a60f92cbfec4'
FILES = {
    'src/bct/review_intake.py': 'c396135d78b5cc1292a58242741db7f388e07cfeeb2fc95722e463bc5c69b24d',
    'src/bct/review_shadow.py': '0d64caf4a6666515d31a974689e9c90e0b2050cf7e764ff9fcafae2bbca5f17d',
    '.github/scripts/review_lead_intake.py': 'ac604a4b743b92a6703d6de565c6a79284400c020a33d42175444a6e98db0939',
}


def executable_ast(raw, *, transport=False):
    tree = ast.parse(raw)
    if transport:
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.ImportFrom) and node.module == 'datetime'
            and [(name.name, name.asname) for name in node.names]
            == [('datetime', None), ('timezone', None)])]
    return ast.dump(tree, include_attributes=False)


def archived_sources():
    try:
        subprocess.run(['git', 'cat-file', '-e', COMMIT + '^{commit}'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', COMMIT], check=True)
    archived = {}
    for path, expected in FILES.items():
        raw = subprocess.check_output(['git', 'show', COMMIT + ':' + path])
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('FROZEN_REVIEW_SOURCE_HASH_MISMATCH')
        if executable_ast(raw, transport=path.endswith('review_shadow.py')) != executable_ast(
                Path(path).read_bytes(), transport=path.endswith('review_shadow.py')):
            raise ValueError('REVIEW_EXECUTABLE_CHANGE_REQUIRES_SEPARATE_VERSION')
        archived[path] = raw
    return archived


def execute(bundle, root):
    root = review_shadow.safe_root(root)
    activation = root / 'shadow-activation.json'
    if not activation.exists():
        return review_shadow.run(bundle, root)
    saved = review.sealed_read(activation)
    if (saved['transport_sha256'] != FILES['src/bct/review_shadow.py']
            or saved['intake_sha256'] != FILES['src/bct/review_intake.py']
            or saved['source_loader_sha256'] != FILES['.github/scripts/review_lead_intake.py']):
        raise ValueError('UNKNOWN_FROZEN_REVIEW_BINDING')
    originals = {str(p.relative_to(root)): p.read_bytes()
                 for p in root.rglob('*') if p.is_file() and p.name not in ('summary.md', '.review-lock')}
    sources = archived_sources()
    previous = {}
    with tempfile.TemporaryDirectory(prefix='bct-frozen-review-') as directory:
        base = Path(directory)
        for path, raw in sources.items():
            target = base / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        try:
            for short in ('review_intake', 'review_shadow'):
                name = 'bct.' + short
                previous[short] = (sys.modules.get(name), getattr(bct, short, None))
                spec = importlib.util.spec_from_file_location(name, base / 'src/bct' / (short + '.py'))
                if spec is None or spec.loader is None:
                    raise RuntimeError('FROZEN_REVIEW_MODULE_UNAVAILABLE')
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                setattr(bct, short, module)
                spec.loader.exec_module(module)
            result = bct.review_shadow.run(bundle, root)
        finally:
            for short, (prior_module, attribute) in previous.items():
                if prior_module is None:
                    sys.modules.pop('bct.' + short, None)
                else:
                    sys.modules['bct.' + short] = prior_module
                if attribute is None:
                    delattr(bct, short)
                else:
                    setattr(bct, short, attribute)
    if any(not (root / path).is_file() or (root / path).read_bytes() != raw
           for path, raw in originals.items()):
        raise ValueError('FROZEN_REVIEW_EXISTING_RECORD_CHANGED')
    proof = {**review.binding(json.loads(Path('review-leads/contract.json').read_text())),
             'archived_commit': COMMIT, 'source_hashes': FILES,
             'executable_ast_equal': True, 'old_files_preserved': len(originals),
             'observed_at': review.now(), 'EARLY_success': False}
    path = root / 'runtime-recovery' / (review.digest(proof) + '.json')
    review.write_first(path, proof)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    result = execute(json.loads(args.input.read_text()), args.state)
    print(json.dumps({'state': 'PASS', 'records': len(result['records']),
                      'alerts': len(result['alerts']), 'EARLY_success_count': 0}))
