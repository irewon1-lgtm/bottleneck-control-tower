"""One atomic publication of bundle, seven-state queue and gzip UI projection."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from bct.future_github import GitHubTransport
from bct.recovery_publication import publish_projection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--recovery-state', type=Path, required=True)
    args = parser.parse_args()
    root = args.recovery_state
    output = args.output_dir
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'],
                                'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    receipt = {'status': 'FAIL', 'actual_execution': True,
               'run_id': os.environ['GITHUB_RUN_ID'],
               'started_at': datetime.now(timezone.utc).isoformat()}
    try:
        changes = [json.loads((output / (name+'-change.json')).read_text())
                   for name in ('bundle', 'queue')]
        versions = json.loads((root/'source-recovery-versions.json').read_text())
        observations = {x['url']: x for x in map(json.loads,
            (root/'source-recovery-attempts.jsonl').read_text().splitlines())}
        result, queue = publish_projection(transport, changes, versions=versions,
            observations=observations, cache=root/'private-source-cache',
            preservation=json.loads(Path('config/bct-recovery-preservation.json').read_text()),
            retained=json.loads((root/'recovery-preservation-seal.json').read_text()),
            run_id=os.environ['GITHUB_RUN_ID'])
        receipt.update(result)
        (output/'operating-queue-versions.json').write_text(
            json.dumps(queue, ensure_ascii=False, indent=2)+'\n')
        return 0
    except Exception as exc:
        # Pending is a concrete failure receipt, never an asserted saved state.
        receipt.update(error_type=type(exc).__name__,
            resume_condition='Read latest roots, rebuild owned projection; restart full verification from Stage 0')
        if type(exc) in (ValueError, RuntimeError):
            receipt['failure_code'] = str(exc)
        return 1
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output/'operating-publication.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({k: receipt.get(k) for k in
            ('status', 'published_commit', 'queue_counts', 'error_type')}))


if __name__ == '__main__':
    raise SystemExit(main())
