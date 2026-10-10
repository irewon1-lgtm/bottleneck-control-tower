"""Actual, bounded public captures. No URL or cached body implies provenance."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .future_body import access_failure, cache_body
from .future_bottleneck import fetch_capture
from .precursor_official_source import verify


def capture(url, root, *, fetch=fetch_capture):
    root=Path(root)
    raw_dir=root/'private-evidence-raw';raw_dir.mkdir(parents=True,exist_ok=True)
    body_dir=root/'private-evidence-cache';body_dir.mkdir(parents=True,exist_ok=True)
    at=datetime.now(timezone.utc).isoformat()
    observation={'url':url,'attempted_at':at,'attempted':True,
                 'environment':'GITHUB_HOSTED_RUNNER','http_request_completed':False}
    try:
        response=fetch(url)
    except Exception as exc:
        diagnostic=access_failure(exc)
        return {**observation,'status':diagnostic['state'],'body_status':'UNAVAILABLE',
                'http_request_completed':diagnostic['category'].startswith('HTTP_'),
                'access_diagnostic':diagnostic}
    # Integrity/schema errors propagate to FAIL, rather than access-wait.
    raw=response['raw'];digest=sha256(raw).hexdigest()
    raw_path=raw_dir/(digest+'.bin')
    if raw_path.exists() and sha256(raw_path.read_bytes()).hexdigest()!=digest:
        raise ValueError('evidence raw cache hash mismatch')
    raw_path.write_bytes(raw)
    proof=verify(raw,url,response['final_url'],at,response['status'],response['content_type'])
    if proof['raw_sha256']!=digest:raise ValueError('evidence response hash mismatch')
    if response['truncated']:
        proof['body_status']='PARTIAL'
        proof.update(provenance='BLOCKED',provenance_verified=False)
        proof['checks']['untruncated_capture']=False
        proof.setdefault('provenance_blockers',[]).append('untruncated_capture')
    body=proof.pop('body')
    if body and cache_body(body_dir,body)!=proof['body_sha256']:
        raise ValueError('evidence body cache hash mismatch')
    return {**observation,'status':proof['body_status'],'body_status':proof['body_status'],
            'body_sha256':proof['body_sha256'],'raw_sha256':digest,
            'observed_final_url':response['final_url'],'http_request_completed':True,
            'http_status':response['status'],'source_proof':proof}


def cached_body(root, observation):
    digest=observation.get('body_sha256')
    if not digest:return ''
    # Reject arbitrary paths even if a malformed journal was restored.
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid evidence body digest')
    path=Path(root)/'private-evidence-cache'/(digest+'.txt')
    if not path.exists():return ''
    body=path.read_text()
    if sha256(body.encode()).hexdigest()!=digest:raise ValueError('evidence body hash mismatch')
    return body
