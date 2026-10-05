"""Read-only research evidence and preservation validation; no A/B/engine rerun."""
import json,hashlib
from pathlib import Path
from bct.review_leads import documents,reference,load_store
from bct.objective_lock import require_objective
root=Path('review-leads/stage2-20261005')
sha=lambda b:hashlib.sha256(b).hexdigest()
baseline=json.loads((root/'baseline-hashes.json').read_text())
changed=[p for p,h in baseline.items() if not Path(p).exists() or sha(Path(p).read_bytes())!=h]
assert not changed,changed
bundle=json.loads((root/'research-input.json').read_text());docs=documents(bundle)
evidence=json.loads((root/'evidence.json').read_text());require_objective(evidence)
for c in evidence['claims']:reference(c['reference'],docs)
receipts=json.loads((root/'followup-receipts.json').read_text())['records'];store=load_store(Path('review-leads/examples-20261005/review-state'))
for r in receipts:
 assert 'status_after' not in r and r['EARLY_success'] is False
 item=next(x for x in store['records'] if x['first']['review_id']==r['review_id'])
 assert item['current_status']=='REVIEW_LEAD'
 assert item['first']['record_sha256']==r['first_record_sha256']
 assert item['first']['first_review_recorded_at']<r['recorded_at']
 assert any(x['record_sha256']==r['record_sha256'] for x in item['history'])
for p in (root/'sources').glob('*.json'):
 if p.name.endswith('.page.json'):continue
 r=json.loads(p.read_text());raw=p.with_suffix('.raw')
 if r.get('http_status')==200:assert sha(raw.read_bytes())==r['sha256']
print(json.dumps({'baseline_files_verified':len(baseline),'changed_existing_files':0,'source_documents':len(docs),'exact_quote_references':len(evidence['claims']),'append_only_followups':len(receipts),'first_cards_unchanged':True,'states_unchanged':True,'ablation_engine_runs':0,'EARLY_success':False,'result':'PASS'},indent=2))
