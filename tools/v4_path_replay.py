import json,pathlib
from bct.v4.research_reading import decode
from bct.v4.evidence_path import save
from bct.v4.research_adapter import analyze as old
from bct.v4.store import Ledger,now
R=pathlib.Path('docs/v4/path-comparison');x=json.loads((R/'langextract-compat.json').read_text());doc=x['source'];w=x['window'];raw=x['receipt']['response']['text'];ps,held=decode(raw,doc,[w]);l=Ledger('var/v4/path-comparison/model-r2-ledger');alt=save(l,[doc],{doc['document_id']:ps},enabled=True);l.close()
items=[{'kind':'PHYSICAL_PRODUCT','role':q['role'],'actuality':q['actuality'],'context':{'quote':q['reference']['quote']},'entity':{'value':q['product']['value'],'quote':q['product']['reference']['quote']},'facts':[]}for q in ps]
legacy=old([doc],{doc['document_id']:{'text':json.dumps({'items':items}),'source':{'windows':[w]}}},enabled=True,mode='BACKFILL',as_of='2026-10-14T12:00:00+00:00')
o={'at':now(),'source':'SAVED_REAL_GROQ_SAME_RAW_REPLAY','new_API_calls':0,'legacy':legacy,'alternative':alt,'source_held':held,'developer_revision':2,'change':'Broad operations word accidentally treated future military replacement as increased supply. Narrow production/delivery predicates now leave it discovery only. No product-name rule added.','decision':'Research connector replaces the legacy pre-discovered-event requirement for precisely located verified events. Product exploration, event acceptance, S-stage separate. LangExtract not selected: identical located records and no quality gain over exact decoder; no further library tuning.','S1_note':'Historical Romanian H215Ms order from an already consumed article; not new LIVE order and not a12–36month supply gap.'}
with(R/'real-output-replay-r2.json').open('x')as f:f.write(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'alternative':alt['counts'],'legacy':legacy['counts'],'source_held':held}))
