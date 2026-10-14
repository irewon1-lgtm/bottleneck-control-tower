"""Offline reuse of existing HTML extraction alternative; no original overwrite."""
import json,pathlib
from bct.v4.cross_industry import alternative_body_view
from bct.v4.store import Ledger,now
R=pathlib.Path('docs/v4/cross-industry');V=pathlib.Path('var/v4/cross-industry')
l=Ledger(V/'ledger');results=[]
with l.worker():
 seen={json.loads(t)['original_document_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_BODY_VIEW'")}
 for t, in list(l.db.execute('SELECT payload FROM documents')):
  d=json.loads(t)
  if d['body']or d.get('body_status')!='UNAVAILABLE'or d['document_id']in seen:continue
  raw=l.db.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone()[0];view=None;error=None
  try:view=alternative_body_view(d,raw)
  except ValueError as e:error=str(e)
  receipt={'original_document_id':d['document_id'],'url':d['origin_url'],'at':now(),'baseline_status':d['body_status'],'source_raw_sha256':d['raw_sha256'],'status':'ACCESS_BLOCKED'if error=='EXPLICIT_ACCESS_RESTRICTION_MARKER'else'DERIVED_PARTIAL'if view else'UNAVAILABLE','reason':error,'new_original':False}
  if view:
   l.capture(view,raw,{'origin':'OFFLINE_EXISTING_TRAFILATURA','original_document_id':d['document_id'],'not_new_source':True});receipt.update(document_id=view['document_id'],body_sha256=view['body_sha256'],body_characters=len(view['body']),extraction=view['extraction'])
  with l.db:l.event('CROSS_BODY_VIEW',receipt)
  results.append(receipt)
l.close();p=R/'body-view-comparison.json'
if results:
 report=json.loads(p.read_text())if p.exists()else{'at':now(),'new_network_requests':0,'views':[]}
 report['views'].extend(results);p.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'compared':len(results),'derived_PARTIAL':sum(x['status']=='DERIVED_PARTIAL'for x in results)}))
