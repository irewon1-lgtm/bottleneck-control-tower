"""Conditional sidecar writes through the existing GitHub contents API."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .future_store import Snapshot, StoreConflict, store_patch


class GitHubTransport:
    def __init__(self, repository, branch, token, *, requester=None):
        if not token:
            raise ValueError('GitHub token unavailable')
        if repository.count('/') != 1 or not branch:
            raise ValueError('repository and branch required')
        self.repository, self.branch, self.token = repository, branch, token
        self.requester = requester or self._request

    def _request(self, method, suffix, payload=None):
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request('https://api.github.com/repos/' + self.repository + suffix,
                          data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 409:
                raise StoreConflict('sidecar SHA changed') from None
            # Never emit tokens, request headers or remote response bodies.
            raise RuntimeError(f'GitHub {method} failed: HTTP {exc.code}') from None

    def read(self, path):
        if path not in ('future-candidates.json', 'future-tracking.json'):
            raise ValueError('unapproved sidecar path')
        value = self.requester('GET', '/contents/' + quote(path) + '?ref=' + quote(self.branch, safe=''))
        blob_sha = value['sha']
        # Contents omits text over 1 MB. Read the immutable blob, never an
        # unpinned second branch read which could race another writer.
        if value.get('encoding') != 'base64':
            value = self.requester('GET', '/git/blobs/' + blob_sha)
        raw = base64.b64decode(value['content'])
        git_sha = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        if git_sha != blob_sha:
            raise ValueError('GitHub content and SHA disagree')
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError('sidecar is not an object')
        return Snapshot(document, blob_sha)

    def write(self, path, document, expected_sha):
        raw = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
        value = self.requester('PUT', '/contents/' + quote(path), {
            'branch': self.branch, 'sha': expected_sha,
            'message': 'Persist v3.3 sidecar change',
            'content': base64.b64encode(raw).decode()})
        return value['content']['sha']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--branch', default='future-bottleneck-data')
    parser.add_argument('--path', choices=['future-candidates.json', 'future-tracking.json'], required=True)
    parser.add_argument('--change', type=Path, required=True)
    parser.add_argument('--candidates', type=Path)
    parser.add_argument('--pending', type=Path, required=True)
    args = parser.parse_args()
    change = json.loads(args.change.read_text())
    transport = GitHubTransport(args.repository, args.branch, os.environ.get('GITHUB_TOKEN'))
    reference = json.loads(args.candidates.read_text()) if args.candidates else None
    result = store_patch(transport, args.path, owner=change['owner'], patch=change['patch'],
                         operation_id=change['operation_id'],
                         version_refs=change.get('version_refs', []), reference_document=reference,
                         prepared_document=change.get('prepared_document'))
    print(json.dumps({'status': result.status, 'reason': result.reason, 'sha': result.sha}))
    if result.status not in ('APPLIED', 'ALREADY_APPLIED'):
        args.pending.parent.mkdir(parents=True, exist_ok=True)
        args.pending.write_text(json.dumps(change, ensure_ascii=False, indent=2) + '\n')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
