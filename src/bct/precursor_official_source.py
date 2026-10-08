"""SEC filing provenance from the official accession listing, not article tags.

Normal articles retain the original verifier. A SEC primary filing requires a
matching CIK/accession/filename and a preserved official submissions response.
Exhibits without their own listing evidence remain BLOCKED; no guessed date.
"""
from datetime import datetime
import fcntl
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from . import future_body, target_acquisition as a
from .collectors.sec.collector import parse_listing, validate_filing
from .collector import MalformedRecord

VERSION = 'sec-original-reader-1'
SEC = re.compile(r'^https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/([A-Za-z0-9._-]+)$')


def metadata(root, url):
    match=SEC.fullmatch(url)
    if not match:return None
    root=Path(root);endpoint=f'https://data.sec.gov/submissions/CIK{int(match[1]):010d}.json'
    path=root/'source-metadata'/(a.digest(endpoint)+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    # Six intake workers can encounter the same issuer. Acquire the official
    # listing once, including a failed attempt, across threads and processes.
    with path.with_suffix('.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        return _metadata(path,root,endpoint,match[1])


def _metadata(path,root,endpoint,cik):
    if path.exists():return json.loads(path.read_text())
    record={'url':endpoint,'acquired_at':a.now()}
    try:
        raw,final,status,ctype=a.fetch(endpoint)
        if final!=endpoint or status!=200:raise ValueError('SEC_METADATA_IDENTITY_MISMATCH')
        value=json.loads(raw)
        if str(value['cik']).zfill(10)!=cik.zfill(10):raise ValueError('SEC_METADATA_CIK_MISMATCH')
        raw_path=root/'raw'/(a.digest(raw)+'.json');raw_path.parent.mkdir(parents=True,exist_ok=True)
        if not raw_path.exists():raw_path.write_bytes(raw)
        record.update(status='CAPTURED',raw_sha256=a.digest(raw))
    except Exception as exc:
        from .precursor_source_search import error_status
        record.update(status=error_status(exc),error=str(exc))
    a.put(path,record)
    return record


def verify(raw,url,final,at,status=200,ctype='text/html',*,metadata_record=None,metadata_raw=None):
    ordinary=a.verify(raw,url,final,at,status,ctype)
    if not SEC.fullmatch(url):
        parser=a.Metadata();parser.feed(raw.decode('utf-8',errors='replace'))
        # Registry URLs may redirect to their publisher's current canonical
        # address. Only an observed same-host redirect AND matching canonical
        # closes identity; no arbitrary cross-site redirect is promoted.
        hosts=[(urlsplit(u).hostname or '').lower().removeprefix('www.') for u in (url,final,parser.canonical or '')]
        if (all(hosts) and len(set(hosts))==1 and a.norm(final)==a.norm(parser.canonical)):
            ordinary=a.verify(raw,final,final,at,status,ctype)
            ordinary['requested_url']=url
            ordinary['identity_reference']={'requested_url':url,'observed_final_url':final,'observed_canonical_url':parser.canonical,'raw_sha256':a.digest(raw)}
        return ordinary
    if not metadata_record or metadata_record.get('status')!='CAPTURED' or not metadata_raw:
        return {**ordinary,'official_source_reader':VERSION,'official_blocker':'OFFICIAL_FILING_LISTING_UNAVAILABLE'}
    match=SEC.fullmatch(url)
    if a.digest(metadata_raw)!=metadata_record['raw_sha256']:raise ValueError('SEC_METADATA_HASH_MISMATCH')
    expected=f'https://data.sec.gov/submissions/CIK{int(match[1]):010d}.json'
    if metadata_record['url']!=expected:raise ValueError('SEC_METADATA_URL_MISMATCH')
    value=json.loads(metadata_raw)
    listing=parse_listing(metadata_raw,match[1].zfill(10),1000)
    matches=[f for f in listing if f.url==url and f.accession.replace('-','')==match[2]]
    if len(matches)!=1:return {**ordinary,'official_source_reader':VERSION,'official_blocker':'ACCESSION_OR_PRIMARY_FILENAME_NOT_LISTED'}
    filing=matches[0]
    try:validate_filing(raw)
    except MalformedRecord:return {**ordinary,'official_source_reader':VERSION,'official_blocker':'INVALID_FILING_BODY'}
    dom=future_body._Document();dom.feed(raw.decode('utf-8',errors='replace'));dom.close()
    bodies=[n for n in future_body._nodes(dom.root) if n.tag=='body']
    body='\n'.join(future_body._blocks(bodies[0])) if len(bodies)==1 and bodies[0].closed else ''
    checks={'http_success':status==200,'same_original_url':url==final,'official_accession_row':True,
            'listing_snapshot_hash':True,'issuer_name_observed':bool(value.get('name')),
            'complete_filing_body':bool(body),'no_access_challenge':not bool(future_body._CHALLENGE.search(body)),
            'original_publication':True,'publication_before_acquisition':filing.filing_date<=at[:10],
            'metadata_before_use':datetime.fromisoformat(metadata_record['acquired_at'])<=datetime.fromisoformat(at)}
    return {**ordinary,'official_source_reader':VERSION,'sec_filing_metadata':metadata_record,
            'origin_id':filing.accession,'origin_publisher':value.get('name') or 'UNKNOWN','canonical_url':url,
            'published_at':filing.filing_date,'published_at_raw':filing.filing_date,'publication_precision':'DATE',
            'body':body,'body_sha256':a.digest(body),'version':a.digest(body),'body_status':'FULL' if body else 'UNAVAILABLE',
            'checks':checks,'provenance':'PASS' if all(checks.values()) else 'BLOCKED','provenance_verified':all(checks.values()),
            'provenance_blockers':[k for k,v in checks.items() if not v]}
