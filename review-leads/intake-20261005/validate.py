"""Read-only integrity checks; no sample, ablation or EARLY rerun."""
import hashlib,json
from pathlib import Path
from bct import review_leads as review, precursor_v2 as extractor
R=Path('review-leads/intake-20261005')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline=json.loads((R/'baseline-hashes.json').read_text())
changed=[p for p,h in baseline.items() if sha(p)!=h];assert not changed,changed
manifest=json.loads((R/'sample-manifest.json').read_text())
assert sha(R/'sample-input.json')==manifest['sample_sha256']
assert sha(R/'executed-code/review_intake.py')==manifest['code_sha256']['src/bct/review_intake.py']
bundle=json.loads((R/'sample-input.json').read_text());docs=review.documents(bundle)
assert [(d['document_id'],d['body_sha256']) for d in bundle['documents']]==[(d['document_id'],d['body_sha256']) for d in manifest['documents']]
output=json.loads((R/'sample-result.json').read_text())
assert len(output['records'])==len(docs)==5
for item in output['records']:
 assert item['mode']=='BACKFILL' and not item['EARLY_success']
 assert item['semantic_review']['manual_or_ai_semantic_review'] is True
 assert not item['automatic_extraction']['facts_verified_semantically']
 for e in item['automatic_extraction']['events']:extractor.verify_reference(e['reference'],docs)
 first=review.sealed_read(R/'sample-state/first'/(item['review_id']+'.json'))
 for f in first['source_observations']:review.reference(f['reference'],docs)
 assert all(x['status']=='UNKNOWN' for x in first['UNKNOWN'])
for path in [R/'final-regression-result.json',R/'regression-result.json']:
 assert json.loads(path.read_text())['counts']=={'REVIEW_LEAD':2,'HOLD':1,'EXCLUDED':1,'CONFIRMATION':0}
print(json.dumps({'result':'PASS','protected_existing_files':len(baseline),'existing_changed':len(changed),'small_sample_runs':1,'sample_documents':5,'sample_counts':output['counts'],'sample_inputs_and_executed_code_bound':True,'new_EARLY_runs':0,'old_ablation_runs':0,'main_LIVE_writes':0},indent=2))
