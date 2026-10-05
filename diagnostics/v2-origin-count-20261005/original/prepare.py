from pathlib import Path
from collections import Counter
import json,hashlib
from bct import precursor_v2 as v
from bct.shadow_input_v2 import load_documents
from bct.shadow_v2 import now
OUT=Path('/workspace/bct-v2-all-verified-batch-20261005');repo=Path('/workspace/bottleneck-control-tower')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
guard={str(p):sha(p) for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts and '.venv' not in p.parts and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}
for p in Path('/workspace/bct-live-state/live-state').rglob('*'):
 if p.is_file():guard[str(p)]=sha(p)
for p in ['/workspace/bct-corpus-acquisition-20261004/official.baseline.json','/workspace/bct-v2-shadow-20261005/input.json']:
 guard[p]=sha(Path(p))
(OUT/'protected-before.json').write_text(json.dumps(guard,indent=2))
roots=[Path(p) for p in ['/workspace/bct-target-evidence-strategy-20261004/final','/workspace/bct-target-evidence-strategy-20261004/trial','/workspace/bct-target-body-acquisition','/workspace/bct-evidence-completeness-20261004','/workspace/bct-targeted-acquisition','/workspace/bct-precursor-pending-808/state/documents','/workspace/bct-new-precursor-20261005/new-only-state/documents','/workspace/bct-new-precursor-20261005/operating-verification/cache-readback/documents','/tmp/bct-existing-canary','/tmp/bct-strict-input-review']]
# Only existing production evidence directories; never tests, synthetic fixtures,
# source retrieval scripts, or 2,808-document screening loops.
files=sorted({p for root in roots for p in root.rglob('*.json') if p.is_file()})
records=[]
def visit(x,p):
 if isinstance(x,dict):
  if x.get('provenance')=='PASS' or x.get('provenance_result')=='PASS' or x.get('provenance_verified') is True:
   records.append((p,x))
  for value in x.values():
   if isinstance(value,(dict,list)):visit(value,p)
 elif isinstance(x,list):
  for value in x:visit(value,p)
for p in files:
 try:visit(json.loads(p.read_text()),p)
 except (ValueError,UnicodeError):pass
base,loader=load_documents('/workspace/bct-v2-shadow-20261005/input.json',provenance_indexes=['/workspace/bct-v2-site-loader-20261005/proof-index.json'])
body_sources={d['body_sha256']:(d['body'],d) for d in base}
for p,x in records:
 if isinstance(x.get('body'),str) and x.get('body_sha256')==v.digest(x['body'].encode()):body_sources[x['body_sha256']]=(x['body'],x)
official=json.loads(Path('/workspace/bct-corpus-acquisition-20261004/official.baseline.json').read_text())['documents']
for d in official:body_sources.setdefault(d['body_sha256'],(d['body'],d))
# Index only retained body files under production evidence roots, not whole-corpus texts.
for root in roots:
 for p in root.rglob('*.body.txt'):
  text=p.read_text();body_sources.setdefault(v.digest(text.encode()),(text,{'body_path':str(p)}))
selected=list((d,'existing-frozen-input/PASS-loader') for d in base)
skips=[];seen_records=Counter()
core=('document_id','body','body_sha256','version','origin_id','origin_url','origin_publisher','provenance_verified','published_at','publication_precision','available_at','origin_family')
for p,x in records:
 digest=x.get('body_sha256') or x.get('snapshot_values',{}).get('body_sha256')
 if not digest:continue
 seen_records[str(p)]+=1
 body_info=body_sources.get(digest)
 if not body_info and x.get('document_id') and x.get('body_chars'):
  file=Path('/workspace/bct-corpus-acquisition-20261004/screening-2000/texts')/(x['document_id']+'.txt')
  if file.exists():
   text=file.read_text()[-x['body_chars']:]
   if v.digest(text.encode())==digest:body_info=(text,{'document_id':x['document_id'],'body_path':str(file)})
 if not body_info:
  skips.append({'proof':str(p),'body_sha256':digest,'reason':'PASS_BODY_NOT_AVAILABLE_AT_RECORDED_HASH'});continue
 body,source=body_info
 # Reuse already normalized metadata for this exact verified body version.
 observed=x.get('original_values',{})
 url=x.get('origin_url') or x.get('original_source_url_verified') or x.get('canonical_url') or x.get('url') or observed.get('canonical_url') or source.get('origin_url') or source.get('original_url')
 pub=x.get('published_at') or x.get('published_at_metadata') or x.get('published_at_original') or observed.get('published_at') or source.get('published_at')
 acquired=x.get('available_at') or x.get('acquired_at') or x.get('acquired_at_snapshot') or x.get('snapshot_values',{}).get('acquired_at') or source.get('available_at')
 publisher=x.get('origin_publisher') or x.get('origin_publisher_observed') or x.get('publisher_observed') or x.get('publisher') or observed.get('publisher') or source.get('origin_publisher')
 origin=x.get('origin_id') or x.get('origin_id_observed') or x.get('article_id') or observed.get('article_id') or source.get('origin_id')
 # Canonical URL observed by a PASS record is a source identity, not a guessed ID.
 if not origin:origin=x.get('canonical_url') or x.get('canonical_url_observed') or x.get('original_source_url_verified')
 did=x.get('document_id') or x.get('source_locator_id') or source.get('document_id') or origin
 d={'document_id':did,'body':body,'body_sha256':digest,'version':x.get('version') or x.get('body_version') or source.get('version') or digest,
    'origin_id':origin,'origin_url':url,'origin_publisher':publisher,'provenance_verified':True,'published_at':pub,
    'publication_precision':x.get('publication_precision') or source.get('publication_precision'),'available_at':acquired}
 if x.get('origin_family'):d['origin_family']=x['origin_family']
 try:v.validate_document(d,now())
 except (KeyError,ValueError,TypeError,AttributeError) as exc:
  skips.append({'proof':str(p),'body_sha256':digest,'reason':str(exc)});continue
 selected.append((d,str(p)))
# Body duplicates and superseded verified versions are excluded without edits to originals.
by_source={};duplicate=0;versions=0;proof_map={}
for d,p in selected:
 d={k:d[k] for k in core if k in d}
 try:v.validate_document(d,now())
 except (KeyError,ValueError,TypeError) as exc:skips.append({'proof':p,'reason':str(exc)});continue
 key=d['origin_url'];old=by_source.get(key)
 proof_map.setdefault(d['body_sha256'],[]).append(p)
 if old:
  if old['body_sha256']==d['body_sha256']:duplicate+=1;continue
  versions+=1
  if v.clock(d['available_at'])<=v.clock(old['available_at']):continue
 by_source[key]=d
by_hash={}
for d in by_source.values():
 if d['body_sha256'] in by_hash:duplicate+=1;continue
 by_hash[d['body_sha256']]=d
docs=list(by_hash.values());assert len({d['document_id'] for d in docs})==len(docs)
input={'documents':docs,'mode':'SHADOW','input_policy':'All available production PASS evidence indexes, exact preserved bodies only; no collection or enrichment.'}
(OUT/'input.json').write_text(json.dumps(input,ensure_ascii=False,indent=2))
report={'pass_metadata_records_seen':len(records),'unique_pass_documents':len(docs),'duplicate_records_excluded':duplicate,'superseded_versions_excluded':versions,'unusable_pass_records':skips,'source_proof_indexes':dict(seen_records),'proof_map':proof_map,'network_requests':0}
(OUT/'input-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:report[k] for k in ['pass_metadata_records_seen','unique_pass_documents','duplicate_records_excluded','superseded_versions_excluded']},indent=2))
print('Unusable records:',Counter(x['reason'] for x in skips))
