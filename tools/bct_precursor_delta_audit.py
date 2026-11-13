"""Verify immutable 3-MB acquisition delta, identify source-backed RSS research."""
from collections import Counter
from pathlib import Path
import hashlib,json,os,re
from urllib.parse import urlsplit
from bct.precursor_collection import stored_documents

RUN=43473259686
RSS_RUN=43472909460
ROOT=Path(os.environ['RUNNER_TEMP'])/'bct-delta-source-audit'
BUNDLE=ROOT/'delta'
MANIFEST=json.loads((BUNDLE/'manifest.json').read_bytes())
if (MANIFEST.get('format')!='bct-cpu-source-delta-1' or MANIFEST.get('status')!='READY'
        or MANIFEST.get('acquisition_run_id')!=RUN or MANIFEST.get('rss_run_id')!=RSS_RUN
        or MANIFEST.get('acquisition_run_attempt')!=1 or MANIFEST.get('rss_run_attempt')!=1):
    raise ValueError('BCT_DELTA_SOURCE_MANIFEST_NOT_EXACT')
for name,expected in MANIFEST['files'].items():
    if name.startswith('/') or '..' in Path(name).parts:
        raise ValueError('BCT_BUNDLE_PATH_UNSAFE')
    p=BUNDLE/name
    if not p.is_file() or p.stat().st_size!=expected['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=expected['sha256']:
        raise ValueError('BCT_BUNDLE_FILE_HASH_MISMATCH:'+name)
rss=json.loads((BUNDLE/'rss-manifest.json').read_bytes())
rss_ids={r['document_id'] for r in rss['documents']}
assert len(rss_ids)==len(rss['documents'])==80
refs={x['document_id']:x for x in MANIFEST.get('documents',[]) if x.get('source_kind')=='RSS'}
if len(refs)!=len([x for x in MANIFEST.get('documents',[]) if x.get('source_kind')=='RSS']):
    raise ValueError('BCT_DUPLICATE_RSS_DOCUMENT_REFERENCE')
holds=[]
docs=stored_documents(BUNDLE,quarantine_invalid=True,holds=holds)
seen={}
for doc in docs:
    id=doc.get('document_id')
    if id not in refs or id not in rss_ids:
        continue
    ref=refs[id]
    if doc.get('provenance')!='PASS' or doc.get('body_sha256')!=ref['body_sha256'] or doc.get('raw_sha256')!=ref['raw_sha256']:
        raise ValueError('BCT_SOURCE_DELTA_DOC_PROOF_MISMATCH')
    if doc['origin_url']!=ref['origin_url']:
        raise ValueError('BCT_DELTA_ORIGIN_URL_MISMATCH')
    if id in seen:raise ValueError('BCT_DUPLICATE_ORIGINAL_DOC_ID')
    seen[id]=doc
stats=Counter()
names=Counter()
event_types=Counter()
samples=[]
records=[]
by_document={}
for docid,doc in seen.items():
    stats['valid_new_originals']+=1
    events=doc.get('precursor_events') or []
    stats['event_count']+=len(events)
    per_doc=[]
    for e in events:
        scope=e.get('scope') if isinstance(e,dict) else None
        raw_product=(scope or {}).get('product') if isinstance(scope,dict) else None
        value=raw_product.get('value') if isinstance(raw_product,dict) else None
        loc=raw_product.get('locator') if isinstance(raw_product,dict) else None
        for kind in e.get('event_types',[]) if isinstance(e,dict) else []:
            event_types[str(kind)]+=1
        if not isinstance(value,str) or not value.strip() or value=='UNKNOWN':
            continue
        if not isinstance(loc,dict):
            continue
        start,end=loc.get('start'),loc.get('end')
        if (type(start) is not int or type(end) is not int
            or not 0<=start<end<=len(doc['body'])
            or doc['body'][start:end]!=value):
            raise ValueError('BCT_PRODUCT_UNBOUND_TO_DOCUMENT_BODY')
        names[value[:100]]+=1
        stats['events_with_source_bound_product']+=1
        per_doc.append({'product':value,'product_offset':loc,'event_types':e.get('event_types',[]),
            'event_id':e.get('event_id')})
    if per_doc:
        stats['docs_with_explicit_product']+=1
        if len(samples)<14:samples.append({
            'host':urlsplit(doc['origin_url']).hostname,
            'original_publisher':str(doc.get('origin_publisher') or '?')[:85],
            'products':sorted({p['product'] for p in per_doc})[:3],
            'event_types':list(sorted({str(t) for p in per_doc for t in p.get('event_types',[])}))[:5]})
    by_document[docid]=per_doc
    records.append({'document_id':docid,'origin_url':doc['origin_url'],
        'origin_publisher':doc.get('origin_publisher'),'published_at':doc.get('published_at'),
        'publication_precision':doc.get('publication_precision'),
        'acquired_at':doc.get('acquired_at'),
        'body_sha256':doc['body_sha256'],'raw_sha256':doc['raw_sha256'],
        'title':str(doc.get('title') or '')[:150],
        'product_events':per_doc})
receipt={'format':'bct-verified-new-precursor-source-candidates-1',
    'source_acquisition_run_id':RUN,'rss_run_id':RSS_RUN,
    'bundle_manifest_sha256':hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),
    'rss_documents':len(rss_ids),'delta_rss_document_references':len(refs),
    'original_verified_in_delta':len(seen),'quarantined_delta_documents':len(holds),
    'status_counts':dict(stats),'event_types':dict(event_types),
    'unique_explicit_products':len(names),'top_products':names.most_common(25),
    'samples':samples,'source_digest':hashlib.sha256('|'.join(sorted(doc['body_sha256'] for doc in seen.values())).encode()).hexdigest(),
    'no_full_text_published':True,'no_shortage_verified':True,
    'no_production_writes':True}
(ROOT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
(ROOT/'candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('BCT_DELTA_VERIFIED_ORIGINAL_PRODUCTS='+json.dumps(receipt,ensure_ascii=False),flush=True)
