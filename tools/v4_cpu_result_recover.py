#!/usr/bin/env python3
"""Verify/recover the approved encrypted failed result. Never run a CPU model."""
import argparse
import json
import os
from pathlib import Path

from bct.v4 import cpu_result_recovery as recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'authenticate'])
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--packet', type=Path, default=Path('var/v4/cpu-private/result/state.gpg'))
    parser.add_argument('--checkpoint', type=Path, default=Path('var/v4/cpu-private/checkpoint'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (os.environ.get('GITHUB_REPOSITORY') != 'irewon1-lgtm/bottleneck-control-tower'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'):
        raise ValueError('RESULT_RECOVERY_REQUIRES_AUTHORIZED_MAIN_DISPATCH')
    if args.action == 'verify':
        result = recovery.verify(args.run_id, args.attempt)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('cache_key=' + result['cache_key'] + '\n')
    else:
        result = recovery.authenticate(args.run_id, args.attempt, args.packet,
                                       args.checkpoint, os.environ.get('BCT_V4_STATE_PASSPHRASE', ''))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream: json.dump(result, stream)
    print('BCT_SAVED_RESULT_RECOVERY_JSON=' + json.dumps(result))


if __name__ == '__main__': main()
