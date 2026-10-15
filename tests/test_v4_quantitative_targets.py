"""Q2 comparisons and storage, not independent future bottleneck performance."""
from copy import deepcopy
import pytest
from bct.v4 import quantitative_targets as targets,quantitative as q,quantitative_private as private
from bct.v4.store import Ledger,sha,file_sha
from bct.v4.evidence_path import TARGET


def fixture_pair():
 d={'target':{k:{'normalized':k+'-same'}for k in TARGET},'lineage':'CUSTOMER_A','unit':'units','period':'2027-10','actuality':'ACTUAL','source_verified':True,'measurement_type':'PHYSICAL','quantity':'12'}
 s=deepcopy(d);s.update(lineage='SUPPLIER_B',quantity='8');return d,s


def test_positive_comparison_only_prepares_existing_engine_and_blocks_mixed_scope():
 d,s=fixture_pair();assert targets.comparable(d,s)[0]
 assert not any(k in d for k in ['S1','S2','S3'])
 for field in TARGET:
  bad=deepcopy(s);bad['target'][field]['normalized']='other'
  assert targets.comparable(d,bad)==(False,'PRODUCT_MISMATCH'if field=='product'else'DIFFERENT_TARGET')
 for field,value,reason in [('lineage','CUSTOMER_A','SAME_OR_UNKNOWN_SOURCE_LINEAGE'),('period','2028-10','PERIOD_MISMATCH_OR_UNKNOWN'),('unit','USD','UNIT_MISMATCH_OR_UNKNOWN'),('actuality','PLAN','PLAN_OR_UNCONFIRMED_NOT_AVAILABLE_SUPPLY'),('quantity',None,'PHYSICAL_QUANTITY_UNKNOWN')]:
  bad=deepcopy(s);bad[field]=value;assert targets.comparable(d,bad)==(False,reason)
 d['unit']=s['unit']='USD';d['measurement_type']=s['measurement_type']='MONEY'
 assert targets.comparable(d,s)==(False,'MONEY_OR_NONPHYSICAL_NOT_QUANTITY')


def test_latest_facility_nameplate_is_not_qualified_supply_noop_restore(tmp_path):
 l=Ledger(tmp_path/'ledger');raw=tmp_path/'source.raw';raw.write_text('{"value":10}')
 m={'source_id':'eia','url':'https://www.eia.gov/electricity/data/eia860m/index.php','sha256':file_sha(raw),'path':str(raw),'acquired_at':'2026-10-15','published_at':'2026-09-24'}
 for month in ['2026-07','2026-08']:
  r=q.observation(m,'plant/generator','solar','nameplate_capacity','10','MW','PHYSICAL',month,{'format':'JSON','path':['value']},attributes={'sheet':'Planned','Planned Operation Year':2028,'Planned Operation Month':6})
  q.commit_page(l,'eia-'+month,m,[r])
 first=targets.save(l,[],as_of='2026-10-15');assert first['added_review_records']==1 and first['latest_facility_observations']==1
 result=targets.prepare(l,[],as_of='2026-10-15');r=result['records'][0]
 assert r['reported_nameplate_MW_sum']=='10'and r['qualified_supply_quantity']is None
 assert r['planned_reported_dates_not_supply_guarantees']==['2028-06']
 before=file_sha(l.path);assert targets.save(l,[],as_of='2026-10-15')['added_review_records']==0;assert file_sha(l.path)==before
 private.checkpoint(l,tmp_path/'checkpoint');l.close()
 private.restore(tmp_path/'checkpoint',tmp_path/'restored');r=Ledger(tmp_path/'restored')
 assert targets.save(r,[],as_of='2026-10-15')['added_review_records']==0
 assert r.db.execute('select count(*)from firsts').fetchone()[0]==0;r.close()
