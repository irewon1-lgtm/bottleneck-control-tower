import json,pathlib,gzip
from bct.v4.structured_changes import snapshot,compare
from bct.v4.store import Ledger,sha,now
R=pathlib.Path('docs/v4/path-comparison');V=pathlib.Path('var/v4/path-comparison');metadata={x['name']:x for x in json.loads((V/'downloads.json').read_text())};snaps=[];l=Ledger(V/'structured-ledger')
for filename,period in(('june2026.xlsx','2026-06'),('july2026.xlsx','2026-07')):
 raw=(V/filename).read_bytes();m=metadata[filename];assert sha(raw)==m['sha256'];p=R/'structured-native';p.mkdir(exist_ok=True);(p/(filename+'.gz')).write_bytes(gzip.compress(raw,mtime=0))
 s=snapshot(raw,period,m['url']);snaps.append(s);body=json.dumps({'period':period,'title':s['titles'],'source':m['url']},ensure_ascii=False,sort_keys=True)
 doc={'document_id':'eia860m-'+period,'body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),'origin_url':m['url'],'origin_id':m['url'],'origin_publisher':'EIA','published_at':'UNKNOWN','acquired_at':now(),'observation_period':period}
 l.capture(doc,raw)
result=compare(*snaps)
with l.db:
 for e in result['events']:l.event('STRUCTURED_CHANGE',e)
count=l.db.execute("select count(*) from events where kind='STRUCTURED_CHANGE'").fetchone()[0];assert count==len(result['events']);l.close();l=Ledger(V/'structured-ledger');assert l.db.execute("select count(*) from events where kind='STRUCTURED_CHANGE'").fetchone()[0]==count;l.backup(V/'structured-backup/v4.sqlite3');l.close()
output={'at':now(),'snapshots':[{'period':s['period'],'url':s['url'],'raw_sha256':s['raw_sha256'],'records':len(s['records']),'duplicates':s['duplicate_ids_quarantined'],'titles':s['titles']}for s in snaps],**result,'storage_requery_after_reopen':count,'source_publication_date':'UNKNOWN_NOT_REPORTING_MONTH','effective_change_vs_revision':'Reported status transition only; not independently established physical commissioning/retirement date or qualified capacity; revisions/data missing not silently interpreted as supply.','global_S1_S2_S3_promotions':0}
(R/'structured-results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'snapshots':output['snapshots'],'counts':result['counts'],'storage_requery':count}))
