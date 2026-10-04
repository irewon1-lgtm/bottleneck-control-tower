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


# The connection limits the JSON request, including base64 expansion, to 16MiB.
# Keep a margin for the envelope and never split an individual data item.
MAX_REQUEST_BYTES = 15 * 1024 * 1024
MAX_SHARD_BYTES = 10 * 1024 * 1024
MANIFEST_FORMAT = 'bct-sharded-sidecar-v1'
SHARD_FORMAT = 'bct-json-shard-v1'


def _raw(document):
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _payload(branch, raw, expected_sha):
    return {'branch': branch, 'sha': expected_sha, 'message': 'Persist v3.3 sidecar change',
            'content': base64.b64encode(raw).decode()}


def _shards(document):
    fields, items = [], []
    for field, value in document.items():
        kind = 'dict' if isinstance(value, dict) else 'list' if isinstance(value, list) else 'value'
        fields.append({'name': field, 'kind': kind})
        entries = value.items() if kind == 'dict' else enumerate(value) if kind == 'list' else [(None, value)]
        for key, entry in entries:
            items.append(json.dumps({'field': field, 'key': key, 'value': entry},
                                    ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())
    prefix = ('{"format":"' + SHARD_FORMAT + '","items":[').encode()
    suffix = b']}\n'
    chunks, current, size = [], [], len(prefix) + len(suffix)
    for item in items:
        if len(prefix) + len(item) + len(suffix) > MAX_SHARD_BYTES:
            raise ValueError('one data item exceeds the shard limit; source left unchanged')
        added = len(item) + bool(current)
        if size + added > MAX_SHARD_BYTES:
            chunks.append((prefix + b','.join(current) + suffix, len(current)))
            current, size, added = [], len(prefix) + len(suffix), len(item)
        current.append(item)
        size += added
    if current:
        chunks.append((prefix + b','.join(current) + suffix, len(current)))
    return fields, chunks


def assemble(manifest, load):
    """Verify immutable shard bytes and restore the original JSON object/order."""
    fields = manifest['fields']
    if len({f['name'] for f in fields}) != len(fields):
        raise ValueError('duplicate manifest field')
    restored, counts = {}, {}
    for field in fields:
        name, kind = field['name'], field['kind']
        if kind not in ('dict', 'list', 'value'):
            raise ValueError('unknown manifest field kind')
        restored[name] = {} if kind == 'dict' else [] if kind == 'list' else None
        counts[name] = 0
    kinds = {f['name']: f['kind'] for f in fields}
    for part in manifest['shards']:
        raw = load(part)
        if len(raw) > MAX_SHARD_BYTES or _sha(raw) != part['sha256']:
            raise ValueError('shard hash/size mismatch')
        value = json.loads(raw)
        if value.get('format') != SHARD_FORMAT or len(value['items']) != part['item_count']:
            raise ValueError('shard format/count mismatch')
        for item in value['items']:
            name, key = item['field'], item['key']
            kind = kinds[name]
            if kind == 'dict':
                if not isinstance(key, str) or key in restored[name]:
                    raise ValueError('duplicate/invalid shard record')
                restored[name][key] = item['value']
            elif kind == 'list':
                if type(key) is not int or key != len(restored[name]):
                    raise ValueError('out-of-order shard record')
                restored[name].append(item['value'])
            else:
                if key is not None or counts[name]:
                    raise ValueError('duplicate/invalid scalar')
                restored[name] = item['value']
            counts[name] += 1
    if (counts != manifest['item_counts'] or sum(counts.values()) != manifest['total_item_count']
            or _sha(_raw(restored)) != manifest['document_sha256']):
        raise ValueError('reconstructed document hash/count mismatch')
    return restored


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
        if data is not None and len(data) > MAX_REQUEST_BYTES:
            raise ValueError('request exceeds safe connection limit')
        request = Request('https://api.github.com/repos/' + self.repository + suffix,
                          data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 404 and method == 'GET':
                raise FileNotFoundError('GitHub object unavailable') from None
            if exc.code == 409:
                raise StoreConflict('sidecar SHA changed') from None
            # Never emit tokens, request headers or remote response bodies.
            raise RuntimeError(f'GitHub {method} failed: HTTP {exc.code}') from None

    def _read_bytes(self, path):
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
        return raw, blob_sha

    def read(self, path):
        if path not in ('future-candidates.json', 'future-tracking.json'):
            raise ValueError('unapproved sidecar path')
        raw, blob_sha = self._read_bytes(path)
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError('sidecar is not an object')
        if document.get('format') == MANIFEST_FORMAT:
            stem = path[:-5]
            for index, part in enumerate(document['shards'], 1):
                expected = f"{stem}.shards/{document['document_sha256']}/{stem}.part-{index:03d}.json"
                if part['path'] != expected:
                    raise ValueError('invalid shard path/order')
            def load(part):
                value = self.requester('GET', '/git/blobs/' + part['git_sha'])
                data = base64.b64decode(value['content'])
                actual = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
                if actual != part['git_sha'] or value['sha'] != actual:
                    raise ValueError('shard Git SHA mismatch')
                return data
            document = assemble(document, load)
        return Snapshot(document, blob_sha)

    def write(self, path, document, expected_sha):
        if path not in ('future-candidates.json', 'future-tracking.json'):
            raise ValueError('unapproved sidecar path')
        raw = _raw(document)
        payload = _payload(self.branch, raw, expected_sha)
        if len(json.dumps(payload).encode()) > MAX_REQUEST_BYTES:
            fields, chunks = _shards(document)  # Preflight every item before any remote write.
            stem, digest = path[:-5], _sha(raw)
            parts = []
            for index, (data, count) in enumerate(chunks, 1):
                name = f'{stem}.shards/{digest}/{stem}.part-{index:03d}.json'
                try:
                    saved, sha = self._read_bytes(name)
                    if saved != data:
                        raise ValueError('immutable staged shard differs')
                except FileNotFoundError:
                    staged = _payload(self.branch, data, None)
                    del staged['sha']
                    result = self.requester('PUT', '/contents/' + quote(name), staged)
                    sha = result['content']['sha']
                    saved, confirmed = self._read_bytes(name)
                    if saved != data or confirmed != sha:
                        raise ValueError('shard readback mismatch')
                parts.append({'path': name, 'sha256': _sha(data), 'git_sha': sha, 'item_count': count})
            counts = {f['name']: len(document[f['name']]) if f['kind'] != 'value' else 1 for f in fields}
            manifest = {'format': MANIFEST_FORMAT, 'document_sha256': digest, 'fields': fields,
                        'shards': parts, 'item_counts': counts, 'total_item_count': sum(counts.values())}
            payload = _payload(self.branch, _raw(manifest), expected_sha)
            if len(json.dumps(payload).encode()) > MAX_REQUEST_BYTES:
                raise ValueError('manifest exceeds safe connection limit')
        # Only this final CAS publishes a generation and any SENT/operation markers.
        value = self.requester('PUT', '/contents/' + quote(path), payload)
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
