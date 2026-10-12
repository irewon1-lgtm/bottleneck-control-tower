"""Verify a real data generation on a dedicated branch, including rollback.

Production branches are read-only here. A successful receipt proves storage
and history preservation, not operating E2E or forecasting performance.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from collections import Counter

from bct.future_github import GitHubTransport, _raw
from bct.recovery_preservation import verify, seal
from bct.recovery_storage_probe import verify_atomic_recovery, observe_published_head


def main():
    repository = os.environ['GITHUB_REPOSITORY']
    run_id = os.environ['GITHUB_RUN_ID']
    token = os.environ['GITHUB_TOKEN']
    output = Path(os.environ['RUNNER_TEMP']) / 'bct-isolated-storage'
    output.mkdir(exist_ok=True)
    source = GitHubTransport(repository, 'future-bottleneck-data', token)
    calls: Counter[str] = Counter()
    original = source.requester

    def counted(method, suffix, payload=None):
        calls[method + ' ' + suffix.split('?', 1)[0]] += 1
        return original(method, suffix, payload)

    source.requester = counted
    head = source.head()
    paths = ('future-candidates.json', 'future-tracking.json')
    snapshots = {p: source.read_at(p, head) for p in paths}
    documents = {p: s.document for p, s in snapshots.items()}
    candidates, tracking = (documents[p] for p in paths)
    baseline = seal(candidates, tracking)
    receipt = {'run_id': run_id, 'code_sha': os.environ['GITHUB_SHA'],
               'status': 'FAIL', 'production_sha': head,
               'production_writes': 0, 'prediction_performance': 'UNVERIFIED',
               'source_root_shas': {p: s.sha for p, s in snapshots.items()},
               'source_document_sha256': {p: hashlib.sha256(_raw(d)).hexdigest()
                                          for p, d in documents.items()}}
    try:
        receipt['historic_preservation'] = verify(candidates, tracking, json.loads(
            Path('config/bct-recovery-preservation.json').read_text()))
        branch = 'ops/bct-storage-probe-' + run_id
        source.create_branch(branch, head)
        probe = GitHubTransport(repository, branch, token, requester=counted)
        receipt['probe_branch'] = branch
        receipt['atomic_recovery'] = verify_atomic_recovery(probe, run_id)
        tested = probe.last_commit
        current = {p: probe.read_at(p, tested) for p in paths}
        verify(current[paths[0]].document, current[paths[1]].document, baseline)
        # Roll back by publishing the exact original documents as a descendant
        # commit. Preserve the entire fault/interleaving history, no forced ref.
        rollback_roots = probe.write_many(deepcopy(documents), {p: s.sha for p, s in current.items()})
        rollback = probe.last_commit
        observe_published_head(probe, rollback, {tested})
        for path in paths:
            restored = probe.read_at(path, rollback)
            if restored.document != documents[path] or restored.sha != snapshots[path].sha:
                raise ValueError('isolated rollback original root/body differs')
        receipt['rollback'] = {'status': 'PASS', 'commit': rollback,
                               'restored_roots': rollback_roots, 'force': False}
        # Production may advance independently; its pinned original generation
        # must remain readable and byte-identical regardless of that advance.
        for path in paths:
            if source.read_at(path, head) != snapshots[path]:
                raise ValueError('pinned production generation changed')
        receipt['production_head_after'] = source.head()
        receipt['status'] = 'PASS'
        return 0
    except Exception as exc:
        receipt['error_type'] = type(exc).__name__
        receipt['error'] = str(exc)
        return 1
    finally:
        receipt['api_calls'] = dict(calls)
        receipt['api_call_total'] = sum(calls.values())
        receipt['retry_observations'] = source.retry_observations
        if 'probe' in locals():
            receipt['probe_retry_observations'] = probe.retry_observations
        (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
