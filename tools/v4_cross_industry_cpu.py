"""Reuse pinned CPU runtime; two whole prose paragraphs, no sector keyword gate."""
import json,pathlib,re,sqlite3,sys
from bct.v4.adapters import CPUExtractor
from bct.v4.store import sha,now
R=pathlib.Path('docs/v4/cross-industry');V=pathlib.Path('var/v4/cross-industry');out=V/'cpu';out.mkdir(exist_ok=True)

def select(doc):
 chunks=[m for m in re.finditer(r'[^\n]+',doc['body'])if 80<=len(m.group())<=1800]
 # Open discovery: leading complete prose, independent of products/industry names.
 return [{'start':m.start(),'end':m.end(),'text':m.group()}for m in chunks[:2]]

if __name__=='__main__':
 c=sqlite3.connect('file:var/v4/cross-industry/ledger/v4.sqlite3?mode=ro',uri=True)
 captured={json.loads(x[0])['document_id']for x in c.execute("SELECT payload FROM events WHERE kind IN ('CROSS_ARTICLE_RESULT','CROSS_BODY_VIEW')")if json.loads(x[0]).get('status')in ('CAPTURED','DERIVED_PARTIAL')}
 blocked={json.loads(t)['document_id']for t, in c.execute("SELECT payload FROM events WHERE kind='CROSS_BODY_VIEW_QUARANTINED'")}
 docs=[json.loads(x[0])for x in c.execute('SELECT payload FROM documents')if json.loads(x[0])['document_id']in captured and json.loads(x[0])['document_id']not in blocked];c.close()
 from v4_cross_industry_analyze import load_inputs
 _,preserved_readings=load_inputs()
 if '--archive-open-check'in sys.argv:
  from v4_cross_industry_analyze import load_inputs
  _,existing=load_inputs();used={json.loads(p.read_text())['document_id']for p in out.glob('*.json')}|set(existing)
  rows=json.loads((V/'existing-documents.json').read_text())
  selection=R/'archive-open-selection.json'
  if selection.exists():
   chosen=set(json.loads(selection.read_text())['document_ids']);docs=[r['doc']for r in rows if r['doc']['document_id']in chosen]
  else:docs=[r['doc']for r in rows if r['doc']['document_id']not in used and r.get('topic_hint')=='UNCLASSIFIED_OPEN_DISCOVERY'][:4]
  if not selection.exists():selection.write_text(json.dumps({'at':now(),'selection':'First4 unread/unclassified preserved records in acquisition inventory order, no product/sector keyword filter; development functionality only, not holdout','document_ids':[d['document_id']for d in docs]},indent=2)+'\n')
 extractor=CPUExtractor('var/v4/repair/cpu/runtime')
 for d in docs:
  windows=select(d);key=sha([d['document_id'],d['body_sha256'],windows]);p=out/(key+'.json')
  if p.exists():continue
  old=preserved_readings.get(d['document_id'],{}).get('CPU',{})
  same=old.get('status')=='PASS'and [(w['start'],w['end'])for w in old.get('selected_windows',[])]==[(w['start'],w['end'])for w in windows]
  try:x=old if same else extractor.extract_windows(d,windows)
  except Exception as e:x={'status':'BLOCKED','reason':type(e).__name__,'selected_windows':windows,'spans':[]}
  result={'document_id':d['document_id'],'body_sha256':d['body_sha256'],'at':now(),'selection':'FIRST_TWO_COMPLETE_PROSE_PARAGRAPHS_NO_SECTOR_OR_SIGNAL_GATE','reused_exact_preserved_input':same,'CPU':x}
  with p.open('x')as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'document_id':d['document_id'],'status':x['status'],'spans':len(x.get('spans',[]))}),flush=True)
