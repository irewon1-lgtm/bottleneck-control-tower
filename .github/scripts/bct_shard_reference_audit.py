"""Read-only reference audit of current sidecar shards; never deletes anything."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from bct.future_github import GitHubTransport, _raw
from bct.recovery_preservation import verify


def main():
    root = Path(os.environ['RUNNER_TEMP']) / 'bct-shard-reference-audit'
    root.mkdir(exist_ok=True)
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data',
                                os.environ['GITHUB_TOKEN'])
    original = transport.requester
    calls = 0
    def read_only(method, suffix, payload=None):
        nonlocal calls
        if method != 'GET':
            raise ValueError('read-only audit forbids every mutation')
        calls += 1
        return original(method, suffix, payload)
    transport.requester = read_only
    head = transport.head()
    commit = transport.requester('GET', '/git/commits/' + head)
    tree = transport.requester('GET', '/git/trees/' + commit['tree']['sha'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('full reference inventory required')
    files = [x for x in tree['tree'] if x['type'] != 'tree']
    if any(x['type'] != 'blob' for x in files):
        raise ValueError('unknown current tree entry type, do not prune')
    by_path = {x['path']: x for x in files}
    paths = ('future-candidates.json', 'future-tracking.json')
    snapshots = {p: transport.read_at(p, head) for p in paths}
    baseline = json.loads(Path('config/bct-recovery-preservation.json').read_text())
    preservation = verify(snapshots[paths[0]].document, snapshots[paths[1]].document, baseline)
    prefix = re.compile(rb'future-(?:candidates|tracking)\.shards/')
    reference = re.compile(rb'future-(?:candidates|tracking)\.shards/[A-Za-z0-9._/-]+\.json')
    referenced = set()
    scanned = []
    def scan(data, name):
        matches = list(reference.finditer(data))
        for position in prefix.finditer(data):
            if not any(m.start() <= position.start() < m.end() for m in matches):
                raise ValueError('unresolved shard-directory reference, do not prune: ' + name)
        referenced.update(m.group().decode('ascii') for m in matches)
        scanned.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    for path in paths:
        scan(_raw(snapshots[path].document), 'ASSEMBLED:' + path)
    for entry in files:
        name = entry['path']
        if re.match(r'^future-(?:candidates|tracking)\.shards/', name):
            continue
        raw, sha = transport._root(name, head)
        if sha != entry['sha']:
            raise ValueError('immutable tree/blob inventory differs')
        if name.endswith('.gz'):
            raw = gzip.decompress(raw)
        elif not name.endswith(('.json', '.md', '.txt')):
            raise ValueError('unknown non-shard file type, do not prune')
        scan(raw, name)
    for path in paths:
        raw, _ = transport._root(path, head)
        manifest = json.loads(raw)
        for part in manifest.get('shards', []):
            if part['path'] not in by_path or by_path[part['path']]['sha'] != part['git_sha']:
                raise ValueError('active manifest shard path/SHA missing')
            referenced.add(part['path'])
    # Any unresolved reference blocks deletion rather than discarding it.
    if referenced - set(by_path):
        raise ValueError('reference outside current inventory; classify before pruning')
    remove = [x for x in files if re.match(r'^future-(?:candidates|tracking)\.shards/', x['path'])
              and x['path'] not in referenced]
    remove_names = {x['path'] for x in remove}
    keep = [x for x in files if x['path'] not in remove_names]
    receipt = {'status': 'PASS', 'actual_remote_execution': True,
               'run_id': os.environ['GITHUB_RUN_ID'], 'code_sha': os.environ['GITHUB_SHA'],
               'production_sha': head, 'production_tree_sha': commit['tree']['sha'],
               'root_shas': {p: s.sha for p, s in snapshots.items()},
               'document_sha256': {p: hashlib.sha256(_raw(s.document)).hexdigest() for p, s in snapshots.items()},
               'preservation': preservation, 'scanned': scanned,
               'all_current_files_before': files, 'delete_candidates': remove,
               'all_current_files_after': keep, 'active_shard_paths': sorted(referenced),
               'before_files': len(files), 'after_files': len(keep),
               'before_logical_bytes': sum(x.get('size', 0) for x in files),
               'after_logical_bytes': sum(x.get('size', 0) for x in keep),
               'removable_logical_bytes': sum(x.get('size', 0) for x in remove),
               'actual_deletions': 0, 'production_ref_writes': 0, 'api_calls': calls,
               'physical_history_bytes_freed': 0,
               'required_before_any_prune': 'All production writers complete; current head still exactly production_sha; preserve backup branch and parent history; conditional non-forced ref and whole retained tree/root readback'}
    (root / 'reference-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('status', 'run_id', 'production_sha', 'before_files',
                     'after_files', 'removable_logical_bytes', 'actual_deletions')}))


if __name__ == '__main__':
    main()
