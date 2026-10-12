"""Actual same-input GitHub transport measurement; production refs read only."""
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import tracemalloc
from urllib.parse import quote

from bct.future_github import GitHubTransport, _raw
from bct.future_review import notification_patch
from bct.future_store import apply_owned_patch
from bct.recovery_preservation import seal, verify

ROOT = Path(os.environ['RUNNER_TEMP']) / 'bct-real-storage-audit'
REPO = os.environ['GITHUB_REPOSITORY']
RUN = os.environ['GITHUB_RUN_ID']
TOKEN = os.environ['GITHUB_TOKEN']
PATHS = ('future-candidates.json', 'future-tracking.json')


def child(label):
    setup = json.loads((ROOT / 'setup.json').read_text())
    if label == 'before':
        spec = importlib.util.spec_from_file_location('bct.bct_baseline_transport', ROOT / 'baseline.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = module.GitHubTransport
    else:
        cls = GitHubTransport
    branch = setup['branches'][label]
    tr = cls(REPO, branch, TOKEN)
    original = tr.requester
    calls = Counter()
    def counted(method, suffix, payload=None):
        calls[method + ' ' + suffix.split('?', 1)[0]] += 1
        if method == 'PATCH' and suffix != '/git/refs/heads/' + quote(branch, safe=''):
            raise ValueError('production ref mutation forbidden')
        if method not in ('GET', 'PATCH') and suffix not in ('/git/blobs', '/git/trees', '/git/commits'):
            raise ValueError('unexpected mutation forbidden')
        return original(method, suffix, payload)
    tr.requester = counted
    head = tr.head()
    if head != setup['production_sha']:
        raise ValueError('measurement branch baseline changed')
    snapshots = {p: tr.read_at(p, head) for p in PATHS}
    documents = {p: json.loads((ROOT / p).read_text()) for p in PATHS}
    verify(snapshots[PATHS[0]].document, snapshots[PATHS[1]].document, setup['seal'])
    input_hashes = {p: hashlib.sha256(_raw(documents[p])).hexdigest() for p in PATHS}
    if input_hashes != setup['input_sha256']:
        raise ValueError('same-input measurement binding differs')
    calls.clear()
    rss_before_write = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    tracemalloc.start()
    start = time.perf_counter()
    roots = tr.write_many(documents, {p: s.sha for p, s in snapshots.items()})
    elapsed = time.perf_counter() - start
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    rss_through_write = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    write_calls = dict(calls)
    saved = tr.last_commit
    if not saved:
        raise ValueError('notification generation was not actually committed')
    after = {p: tr.read_at(p, saved) for p in PATHS}
    for p in PATHS:
        if _raw(after[p].document) != _raw(documents[p]) or after[p].sha != roots[p]:
            raise ValueError('actual immutable body/root readback differs')
    verify(after[PATHS[0]].document, after[PATHS[1]].document, setup['seal'])
    if notification_patch(after[PATHS[0]].document, after[PATHS[1]].document,
                          now=setup['clock']) is not None:
        raise ValueError('same notification was not deduplicated')
    notification = after[PATHS[0]].document['notifications'][setup['notification_id']]
    if notification['state'] != 'READY':
        raise ValueError('receipt must not invent actual sending or receipt')
    result = {'status': 'PASS', 'label': label, 'actual_remote_execution': True,
              'branch': branch, 'commit': saved, 'roots': roots,
              'input_sha256': input_hashes, 'write_seconds': elapsed,
              'write_peak_python_allocation_bytes': peak,
              'resident_peak_before_write_bytes': rss_before_write,
              'resident_peak_through_write_bytes': rss_through_write,
              'resident_peak_after_readback_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'resident_peak_scope': 'Linux ru_maxrss, whole fresh child process including initial baseline/input load; measured through write and after readback; excludes parent driver and CPU model',
              'write_api_calls': write_calls, 'write_api_call_total': sum(write_calls.values()),
              'readback_inclusive_api_call_total': sum(calls.values()),
              'notification_state': 'READY', 'same_notification_suppressed': True,
              'production_ref_mutation_calls': 0, 'actual_notifications_sent': 0,
              'user_receipt_verified': False}
    (ROOT / (label + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('label', 'status', 'write_seconds', 'write_api_call_total')}))


def main():
    if len(sys.argv) == 2:
        child(sys.argv[1])
        return
    ROOT.mkdir(exist_ok=True)
    tr = GitHubTransport(REPO, 'future-bottleneck-data', TOKEN)
    head = tr.head()
    snapshots = {p: tr.read_at(p, head) for p in PATHS}
    c, t = (snapshots[p].document for p in PATHS)
    baseline = seal(c, t)
    verify(c, t, json.loads(Path('config/bct-recovery-preservation.json').read_text()))
    clock = datetime.now(timezone.utc).isoformat()
    patch = notification_patch(c, t, now=clock)
    if patch is None:
        raise ValueError('actual existing notification is suppressed; do not fabricate new inputs')
    notification_id = next(iter(patch['notifications']))
    changed = apply_owned_patch(c, owner='notification', patch=patch,
                               operation_id='actual-notification-audit-' + RUN,
                               prepared_document=c)
    for key in set(c) | set(changed):
        if key not in ('operations', 'notifications') and c.get(key) != changed.get(key):
            raise ValueError('notification changed original operational field')
    documents = dict(zip(PATHS, (changed, t)))
    for p, document in documents.items():
        (ROOT / p).write_bytes(_raw(document))
    old_sha = 'cbe1f488db80f2232dd7ab99c598fe72ef55e41a'
    old = tr.requester('GET', '/contents/src/bct/future_github.py?ref=' + old_sha)
    raw = base64.b64decode(old['content'])
    if hashlib.sha1(('blob ' + str(len(raw)) + '\0').encode() + raw).hexdigest() != old['sha']:
        raise ValueError('baseline Git blob SHA differs')
    (ROOT / 'baseline.py').write_bytes(raw)
    branches = {label: 'ops/bct-storage-audit-' + RUN + '-' + label
                for label in ('warmup', 'before', 'after')}
    setup = {'production_sha': head, 'seal': baseline, 'clock': clock,
             'notification_id': notification_id, 'branches': branches,
             'input_sha256': {p: hashlib.sha256(_raw(d)).hexdigest() for p, d in documents.items()},
             'baseline_code_sha': old_sha, 'baseline_git_blob': old['sha'],
             'after_module_sha256': hashlib.sha256(Path('src/bct/future_github.py').read_bytes()).hexdigest()}
    (ROOT / 'setup.json').write_text(json.dumps(setup, indent=2) + '\n')
    for label, branch in branches.items():
        tr.create_branch(branch, head)
        # Warmup links identical output objects before both measured cases.
        # This removes object propagation as a timing-condition difference.
        subprocess.run([sys.executable, __file__, label], check=True)
    before, after = (json.loads((ROOT / (label + '.json')).read_text()) for label in ('before', 'after'))
    if before['roots'] != after['roots'] or before['input_sha256'] != after['input_sha256']:
        raise ValueError('before/after storage outputs differ')
    for p in PATHS:
        if tr.read_at(p, head) != snapshots[p]:
            raise ValueError('immutable original production source changed')
    receipt = {'status': 'PASS', 'actual_remote_execution': True, 'run_id': RUN,
               'code_sha': os.environ['GITHUB_SHA'], 'production_sha': head,
               'production_ref_writes': 0, 'force_pushes': 0,
               'measurement_scope': 'Same real production documents, fixed notification output, fresh processes, pre-linked same objects, timed write_many only; excludes setup/readback and model CPU',
               'baseline_code_sha': old_sha, 'before': before, 'after': after,
               'original_preservation': 'PASS', 'notification_READY_and_dedup': 'PASS',
               'external_notification_send_or_receipt': 'NOT_RUN',
               'prediction_performance': 'UNVERIFIED',
               'production_head_after': tr.head()}
    (ROOT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('status', 'run_id', 'production_ref_writes', 'notification_READY_and_dedup')}))


if __name__ == '__main__':
    main()
