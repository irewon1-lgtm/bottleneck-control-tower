"""Read-only official source sample checks plus existing Ledger backup/restore.

Development samples are not an independent evaluation or a whole-corpus claim.
No API calls or CPU inference. Source3/operational databases remain untouched.
"""
import json,gzip,hashlib,sqlite3,zipfile,xml.etree.ElementTree as E
from pathlib import Path
from io import BytesIO
from collections import defaultdict,Counter
from decimal import Decimal
from bct.v4.store import Ledger,sha,file_sha,now
from bct.v4.quantitative import records,backup_restore,verify_locator,number
from bct.v4.structured_changes import NS,REL
R=Path('var/v4/quantitative/q1');D=Path('docs/v4/quantitative')

def cells(raw,targets):
 z=zipfile.ZipFile(BytesIO(raw));strings=[]
 if 'xl/sharedStrings.xml'in z.namelist():
  for _,n in E.iterparse(z.open('xl/sharedStrings.xml'),events=('end',)):
   if n.tag==NS+'si':strings.append(''.join(t.text or ''for t in n.iter(NS+'t')));n.clear()
 links={n.get('Id'):n.get('Target')for n in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};out={}
 for s in E.fromstring(z.read('xl/workbook.xml')).find(NS+'sheets'):
  wanted={c for sn,c in targets if sn==s.get('name')}
  if not wanted:continue
  target=links[s.get(REL+'id')];path=target.lstrip('/')if target.startswith('/')else'xl/'+target
  for _,n in E.iterparse(z.open(path),events=('end',)):
   if n.tag!=NS+'c':continue
   coord=n.get('r')
   if coord in wanted:
    v=n.find(NS+'v');v=v.text if v is not None else None
    if n.get('t')=='s'and v is not None:v=strings[int(v)]
    elif n.get('t')=='inlineStr':v=''.join(t.text or ''for t in n.iter(NS+'t'))
    out[(s.get('name'),coord)]=v;wanted.remove(coord)
   n.clear()
   if not wanted:break
 return out


def main():
 l=Ledger(R/'ledger');rows=records(l);group=defaultdict(list)
 # Fixed review grouping policy: source/type/status/sign/zero and each original unit;
 # first and last records in every populated group. No favorable-only selection.
 for item in rows:
  r=item['record'];v=r['value_decimal_or_null'];sign='UNKNOWN'if v is None else'ZERO'if Decimal(v)==0 else'NEGATIVE'if Decimal(v)<0 else'POSITIVE'
  group[(r['source_id'],r['measurement_type'],r['status'],sign,r['unit_original'])].append(item)
 samples={r['id']:r for g in group.values()for r in [g[0],g[-1]]};rawmap={}
 for p in [*(R/'discovery').glob('*.json'),*(R/'requests').glob('*.json')]:
  m=json.loads(p.read_text())
  if m.get('status')==200 and m.get('sha256'):
   path=Path(m.get('path')or p.with_suffix('.raw'))
   if path.exists():rawmap[m['sha256']]=path
 findings=[];verified=[];xl=defaultdict(list)
 for item in samples.values():
  r=item['record'];loc=r['source_locator']
  if loc['format']=='XLSX':xl[r['raw_or_safe_payload_hash']].append(item);continue
  try:verify_locator(r,rawmap[r['raw_or_safe_payload_hash']].read_bytes());verified.append({'id':item['id'],'source':r['source_id'],'locator':loc,'value':r['value_original'],'unit':r['unit_original'],'period':[r['period_start'],r['period_end']]})
  except Exception as e:findings.append({'id':item['id'],'source':r['source_id'],'error':type(e).__name__,'detail':str(e)[:100]})
 for h,items in xl.items():
  try:
   raw=rawmap[h].read_bytes();assert sha(raw)==h;values=cells(raw,{(x['record']['source_locator']['sheet'],x['record']['source_locator']['cell'])for x in items})
   for item in items:
    r=item['record'];loc=r['source_locator'];actual=values[(loc['sheet'],loc['cell'])];val,flag=number(actual)
    if r.get('attributes',{}).get('footnote_pointer'):val=None
    if val is None:ok=r['value_decimal_or_null']is None and (str(actual)==r['value_original']or actual is None and r['value_original']is None)
    else:ok=r['value_decimal_or_null']is not None and Decimal(val)==Decimal(r['value_decimal_or_null'])
    if not ok:findings.append({'id':item['id'],'source':r['source_id'],'error':'XLSX_NUMERIC_OR_SUPPRESSION_MISMATCH','locator':loc})
    else:verified.append({'id':item['id'],'source':r['source_id'],'locator':loc,'native_cell_lexeme':actual,'value':r['value_original'],'unit':r['unit_original'],'period':[r['period_start'],r['period_end']]})
  except Exception as e:findings.append({'raw_hash':h,'error':type(e).__name__,'detail':str(e)[:100]})
 # Retain mistaken early draft periods as history; explicitly withhold them from exports.
 historical_awards=[x['id']for x in rows if x['record']['source_id']=='usaspending'and x['record']['metric']=='award_amount'and x['record']['period_start']!='UNKNOWN']
 with l.worker(),l.db:
  l.event('QUANTITATIVE_VALIDATION',{'policy':'Q1-contract-start-is-not-observation-period-1','record_ids':historical_awards,'quality_state':'HELD_OBSERVATION_PERIOD_UNKNOWN','reason':'Early draft carried contract start as measurement period; original draft immutable, not accepted as time-qualified demand. Current parser uses UNKNOWN and keeps contract dates separately.','originals_modified':False})
 proof=R/'verification';proof.mkdir(exist_ok=True);path=proof/'backup/v4.sqlite3'
 if path.exists():raise ValueError('VERIFICATION_DESTINATION_EXISTS_CHOOSE_NEW_REVIEW_RUN')
 before=file_sha(l.path)
 try:backup_restore(l,path,expected_current_hash='0'*64)
 except ValueError as e:
  assert str(e)=='LOCAL_STATE_CAS_HASH_CHANGED'and not path.exists()and file_sha(l.path)==before
 else:raise ValueError('EXPECTED_CAS_REFUSAL_DID_NOT_HAPPEN')
 result=backup_restore(l,path,expected_current_hash=before);l.close()
 # A truly new process must be launched separately for the backup receipt.
 archive=proof/'checkpoint.sqlite3.gz'
 with path.open('rb')as src,archive.open('xb')as dst:
  with gzip.GzipFile(fileobj=dst,mode='wb',mtime=0)as gz:
   import shutil;shutil.copyfileobj(src,gz)
 assert archive.stat().st_size<=16*1024**2
 out={'plan_id':'BCT-V4-Q-1.0','step':'Q1','at':now(),'sample_policy':'Before scoring: first+last of every source/type/status/sign/unit group; immutable stored outputs, not independent model evaluation.','samples':len(samples),'exact_value_locator_checks_passed':len(verified),'findings':findings,'checks':verified,'unit_period_limits':['USAspending source publication time unknown; contract dates not delivery/observation period. Early draft award periods explicitly held.','EIA July publication date unknown; nominal MW not qualified available supply.','USGS publication date unknown; workbook data-through date is not publication. Census-attributed trade shares lineage.','TED money currency exact raw field; lot quantities/units require explicit XML relations. No inferred pairing.'],'unit_period_full_corpus_verdict':'PARTIAL_NOT_100_PERCENT_ACCURACY','historical_award_period_drafts_held':len(historical_awards),'local_backup_restore':result,'local_storage_CAS_refusal_then_recovery':'PASS_ACTUAL_Q1_SQLITE_NOT_REMOTE_GIT_CAS','gzip_checkpoint_bytes':archive.stat().st_size,'private_remote_store_restore':'BLOCKED_CONFIGURED_GITHUB_CREDENTIAL_HTTP401_NOT_RETESTED','entire_original_research_DB_restore':False,'AI_calls':0,'CPU_windows':0,'new_stage_candidates':0}
 (D/'quality-evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['checks','unit_period_limits']}))

if __name__=='__main__':main()
