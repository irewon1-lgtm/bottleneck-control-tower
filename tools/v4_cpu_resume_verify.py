#!/usr/bin/env python3
"""Explicit one-time real-source CPU development check, never a scheduler.
Reuses existing source/model/runtime. Requires a new output root; no reinstall,
network collection, original1210/67 replay, live candidate or provider API.
"""
import json,sqlite3,pathlib,datetime,resource,time
from bct.v4 import cpu_automation as q,cpu_resume as resume,cpu_operations as op
from bct.v4.adapters import html_views,CPUExtractor
from bct.v4.store import sha,file_sha
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);args=p.parse_args()
root=args.root
if not(root/'prepared/checkpoint').exists():raise ValueError('PREPARED_SOURCE_SEPARATED_CHECKPOINT_REQUIRED')
with sqlite3.connect('file:var/v4/supply-linkage/ledger/v4.sqlite3?mode=ro',uri=True)as db:
 d=json.loads(db.execute("select payload from documents where id like 'link-primary-9bd6%' ").fetchone()[0])
 raw=db.execute('select data from blobs where id=?',(d['raw_sha256'],)).fetchone()[0]
assert sha(raw)==d['raw_sha256'] and html_views(raw)['trafilatura']==d['body']
basis=d['primary_source_basis']
d['native_body_extractor']='existing-trafilatura-tables-v1'
d['checks']={'cached_official_HTTP200':basis['HTTP']==200,'raw_hash_matches':sha(raw)==d['raw_sha256'],
 'native_body_matches_existing_extractor':html_views(raw)['trafilatura']==d['body'],
 'native_publication_literal':basis['date_literal'].encode()in raw,
 'publication_before_acquisition':datetime.date.fromisoformat(d['published_at'])<=datetime.datetime.fromisoformat(d['acquired_at']).date(),
 'official_primary_previously_verified':d['primary_source_verified']is True}
assert all(d['checks'].values())
cache=root/'qualified-cache';(cache/'documents').mkdir(parents=True,exist_ok=False);(cache/'raw').mkdir()
d['raw_path']=d['raw_sha256']+'.html';(cache/'raw'/d['raw_path']).write_bytes(raw)
(cache/'documents'/('source.json')).write_text(json.dumps(d))
policy=json.loads(pathlib.Path('docs/v4/cpu-automation/preflight/publication-policy.json').read_text())
assert resume.transient_allowed(d,policy)
# Use a separate restored derivative, never mutate the frozen original.
op.restore(root/'prepared/checkpoint',root/'new-input-run')
l=q.open_queue(root/'new-input-run');prior=resume.summary(l)
manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':d['document_id'],'url':d['origin_url']}]}
clock=time.monotonic()
imports=q.ingest_delta(l,manifest,cache,upstream_run_id='MANUAL_SOURCE_SEPARATED_RESTART_TEST',storage_policy=policy,source_separated=True)
assert imports[0]['status']=='QUEUED',imports
result=q.work(l,extractor=CPUExtractor('var/v4/repair/cpu/runtime'),max_windows=24,seconds=45)
remaining=q.state(l);l.close()
separated=resume.export_state(root/'new-input-run/v4.sqlite3',root/'after-new-input')
l=q.open_queue(root/'after-new-input');audit=resume.audit(l);op.checkpoint(l,root/'after-new-checkpoint')
assert not q.work(l)['new_windows'];l.close()
output={'document_id':d['document_id'],'origin_url':d['origin_url'],'source_reused':'Existing official acquisition; not a new fetch or any of the completed1210/67 inputs',
 'native_sha256':d['raw_sha256'],'body_sha256':d['body_sha256'],'body_characters':len(d['body']),
 'input_extractor':d['native_body_extractor'],'source_checks':d['checks'],'new_CPU_windows':result['new_windows'],
 'actually_read_characters':result.get('actually_read_characters',0),'CPU_coverage':remaining['coverage'],
 'CPU_failed_windows':remaining['failed_windows'],'pending_CPU_windows':remaining['pending_windows'],
 'before':prior,'after':separated,'source_free_audit':audit['status'],
 'wall_seconds':time.monotonic()-clock,'process_peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
 'model_downloads':0,'AI_calls':0,'API_cost_KRW':0,'automatic_stage_promotion':False,
 'not_a_scheduled_run':True,'seven_day_started':False}
args.output.write_text(json.dumps(output,indent=2));print(json.dumps({k:v for k,v in output.items()if k not in ('CPU_coverage','before','after')},indent=2))
