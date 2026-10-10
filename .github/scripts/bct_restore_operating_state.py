"""Restore the newest completed recovery artifact using its GitHub SHA256.

The authenticated request is limited to api.github.com. Artifact redirects
are followed with a new unauthenticated request; tokens never reach blob hosts.
An invalid newest checkpoint fails closed rather than silently selecting stale
source classifications from an older successful run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
import zipfile

from bct.recovery_restore import verify_restored, LATEST_ROOT_STATE


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = os.environ['GITHUB_REPOSITORY']
    if repository != 'irewon1-lgtm/bottleneck-control-tower':
        raise ValueError('unexpected production repository')
    prefix = 'https://api.github.com/repos/'+repository
    headers = {'Authorization': 'Bearer '+os.environ['GITHUB_TOKEN'],
               'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    def api(suffix):
        with urlopen(Request(prefix+suffix, headers=headers), timeout=30) as response:
            return json.load(response)
    selected = None
    for page in range(1, 11):
        runs = api('/actions/runs?branch=ops%2Frecovery-20261010&per_page=100&page='+str(page))['workflow_runs']
        for run in runs:
            if run['status'] == 'completed' and run['path'] == '.github/workflows/bct-recovery.yml':
                selected = run
                break
        if selected or len(runs) < 100:
            break
    if not selected:
        raise RuntimeError('completed recovery checkpoint unavailable')
    artifacts = api('/actions/runs/'+str(selected['id'])+'/artifacts')['artifacts']
    selected_artifacts = [a for a in artifacts if a['name'] == 'bct-recovery-checkpoint-'+str(selected['id'])]
    if len(selected_artifacts) != 1 or selected_artifacts[0]['expired']:
        raise RuntimeError('newest completed recovery artifact missing or expired')
    artifact = selected_artifacts[0]
    expected = artifact.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', expected):
        raise ValueError('GitHub artifact digest required before restore')
    try:
        # Do not forward the Authorization header on the redirect.
        build_opener(NoRedirect).open(Request(prefix+'/actions/artifacts/'+str(artifact['id'])+'/zip',
                                              headers=headers), timeout=30)
    except HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise
        location = exc.headers['Location']
    else:
        raise RuntimeError('expected signed artifact redirect')
    parsed = urlparse(location)
    if (parsed.scheme != 'https' or not parsed.hostname
            or not parsed.hostname.endswith(('.blob.core.windows.net', '.actions.githubusercontent.com'))):
        raise ValueError('unexpected artifact download host')
    archive = args.output.parent/'operating-recovery-artifact.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with urlopen(location, timeout=30) as response, archive.open('wb') as stream:
        while chunk := response.read(1024*1024):
            size += len(chunk)
            if size > 512*1024**2:
                raise ValueError('artifact download bound exceeded')
            stream.write(chunk)
            digest.update(chunk)
    if 'sha256:'+digest.hexdigest() != expected:
        raise ValueError('downloaded artifact SHA256 differs from GitHub metadata')
    unpack(archive, args.output)
    checkpoint = json.loads((args.output/'checkpoint.json').read_text())
    if str(checkpoint['run_id']) != str(selected['id']):
        raise ValueError('artifact checkpoint execution identity differs')
    required = ('checkpoint.json', 'source-recovery-attempts.jsonl',
                'source-recovery-versions.json', 'recovery-preservation-seal.json')
    pins = {name: hashlib.sha256((args.output/name).read_bytes()).hexdigest() for name in required}
    pins.update({name: hashlib.sha256((args.output/name).read_bytes()).hexdigest()
                 for name in LATEST_ROOT_STATE if (args.output/name).exists()})
    receipt = verify_restored(args.output, pins)
    receipt.update(artifact_id=artifact['id'], artifact_sha256=digest.hexdigest(),
        artifact_run_id=selected['id'], actual_execution=True,
        observed_at=datetime.now(timezone.utc).isoformat())
    (args.output/'operating-state-restore.json').write_text(json.dumps(receipt, indent=2)+'\n')
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
