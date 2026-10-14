"""Exactly one development compatibility call; output appended, never retried."""
import json,pathlib
from bct.v4.research_reading import langextract_call,generate,decode,PROMPT
from bct.v4.evidence_path import analyze
from bct.v4.store import Ledger,now
R=pathlib.Path('docs/v4/path-comparison');P=R/'langextract-compat.json'
assert not P.exists()
row=next(r for r in json.loads(pathlib.Path('docs/v4/stage4-corpus/round2/inputs.json').read_text())['documents'] if r.get('source') and 'order' in r['source']['windows'][0]['text'].casefold())
# Frozen original transmitted windows only: no source-contact expansion.
window=row['source']['windows'][0];text=window['text'];config=json.loads(pathlib.Path('docs/v4/stage4-corpus/round3/request-config.json').read_text());receipt={}
l=Ledger('var/v4/sequential/api-ledger')
with l.worker():
 def callback(prompt):
  x=generate(l,config,prompt,row['doc'],[window],phase='development');receipt.update(x)
  if x['status']!='RECEIVED':raise RuntimeError(x['status'])
  return x['response']['text']
 try:
  output,calls=langextract_call(text,callback)
  aligned=[]
  for e in output.extractions:
   q=e.extraction_text;a,b=e.char_interval.start_pos,e.char_interval.end_pos
   assert str(e.alignment_status)=='AlignmentStatus.MATCH_EXACT'and text[a:b]==q
   aligned.append({'text':q,'start':a,'end':b,'status':str(e.alignment_status)})
  proposals,held=decode(receipt['response']['text'],row['doc'],[window]);result=analyze([row['doc']],{row['doc']['document_id']:proposals},enabled=True)
  status='PASS_COMPATIBILITY_NOT_ACCURACY'
 except Exception as e:status='BLOCKED';aligned=[];held=[{'reason':str(e)}];result=None;calls=int(bool(receipt.get('attempt_id')))
finally_close=False
l.close()
report={'at':now(),'status':status,'document_id':row['document_id'],'source':row['doc'],'window':window,'receipt':receipt,'langextract_provider_infer_calls':calls,'extraction_passes':1,'workers':1,'fetch_urls':False,'fuzzy_alignment':False,'retries':0,'aligned':aligned,'held':held,'alternative':result,'license':'Apache-2.0','version':'1.7.1','meaning':'Compatibility/source alignment and research event flow only; consumed development input, not independent performance.'}
P.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':status,'calls':calls,'receipt_status':receipt.get('status'),'aligned':aligned,'counts':result['counts']if result else None,'held':held},ensure_ascii=False))
