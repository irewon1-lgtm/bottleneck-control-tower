"""Restore the authenticated current resume input, including preserved copies.

The release/request origin stays exact. Input restore never renews Gate proof,
selects an unrelated historical branch, or writes an operating Git ref.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler
import zipfile

import recovery_artifacts as transport


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def unpack(archive, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 15000 or sum(x.file_size for x in entries) > 1024**3:
            raise ValueError('artifact extraction bound exceeded')
        seen = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16) or path.as_posix() in seen):
                raise ValueError('unsafe or duplicate artifact entry')
            seen.add(path.as_posix())
        if destination.exists() and any(destination.iterdir()):
            raise ValueError('operating restore destination must be empty')
        destination.mkdir(parents=True, exist_ok=True)
        bundle.extractall(destination)


def restore_current(root, output, *, api=None):
    root, output = Path(root), Path(output)
    request = json.loads((root/'.github/bct-recovery-request.json').read_text())
    release = json.loads((root/'config/bct-operating-release.json').read_text())
    origin = transport.resume_origin(request, release)
    if request.get('resume_input_only', False):
        raise ValueError('OPERATING_RESTORE_SUCCESSFUL_RELEASE_INPUT_REQUIRED')
    api = api or transport.API()
    repository = api.read('')
    if not repository or repository.get('private') is not False or repository.get('visibility') != 'public':
        raise ValueError('ARCHIVE_PUBLIC_STANDARD_ACTIONS_REQUIRED')
    result = transport.restore(api, origin, request, output)
    receipt = {**result['restore'], 'artifact_id': origin['artifact_id'],
        'artifact_sha256': origin['sha256'], 'artifact_run_id': origin['run_id'],
        'transport': result['transport'], 'actual_execution': True,
        'new_gate_execution': False, 'release_proof_renewed': False,
        'observed_at': datetime.now(timezone.utc).isoformat()}
    (output/'operating-state-restore.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ['GITHUB_REPOSITORY'] != transport.REPOSITORY:
        raise ValueError('unexpected production repository')
    receipt = restore_current(Path('.'), args.output)
    print(json.dumps({k: receipt[k] for k in ('status', 'artifact_id', 'artifact_run_id', 'cache_inventory_sha256')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # A download failure must not print a signed URL or credentials.
        failure: dict[str, Any] = {'status': 'FAIL', 'error_type': type(exc).__name__}
        if isinstance(exc, HTTPError):
            failure['http_status'] = exc.code
            failure['response_headers'] = {key: exc.headers.get(key) for key in
                ('Retry-After', 'x-ratelimit-remaining', 'x-ratelimit-reset', 'x-github-request-id')}
        print(json.dumps(failure))
        raise SystemExit(1)
