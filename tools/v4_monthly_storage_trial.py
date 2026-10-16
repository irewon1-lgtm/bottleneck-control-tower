"""Actual monthly research save/read trial; no scheduler or source collection."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from bct.objective_lock import stamp_export
from bct.v4 import monthly_storage as ms, quantitative_private as private
from bct.v4 import quantitative as q, quantitative_counterpart as counterpart
from bct.v4.store import Ledger, sha, file_sha
from v4_release_archive_trial import ROOT, prepare, read, write, password, inventory


def monthly(**kw):
    return ms.Monthly(os.environ['BCT_V4_PRIVATE_STATE_TOKEN'],password(),**kw)


def state(db):
    kinds=['QUANTITATIVE_PAGE_COMMITTED','QUANTITATIVE_SOURCE_FAILURE','QUANTITATIVE_RELATION_TASK',
           'QUANTITATIVE_COUNTERPART_REVIEW','QUANTITATIVE_PRODUCT_FACT','QUANTITATIVE_TARGET_REVIEW']
    return {k:{'rows':len(rows),'sha256':sha(rows)}for k in kinds
            for rows in [db.execute('SELECT seq,at,payload FROM events WHERE kind=? ORDER BY seq',(k,)).fetchall()]}


def seed():
    m=monthly();old=read('legacy.json');current=m.head()
    if current is None:
        cursor={'backend':'git-seed','legacy_parent':old['parent'],'sqlite_sha256':old['verified']['sqlite_sha256']}
        result=m.publish(ROOT/'legacy-checkpoint',cursor)
    else:
        result={'storage':current,'existing_month_preserved':True}
    write('monthly-seed.json',result);print('Monthly research full seed is present; original Git unchanged')


def append():
    started=time.monotonic();m=monthly();got=m.receive(ROOT/'monthly-input')
    print('Monthly append input received seconds='+str(round(time.monotonic()-started,2)),flush=True)
    private.restore(ROOT/'monthly-input',ROOT/'monthly-ledger')
    l=Ledger(ROOT/'monthly-ledger');before=state(l.db)
    reason='MONTHLY_RELEASES_RESEARCH_PRIMARY_'+m.month
    exists=l.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION'AND json_extract(payload,'$.reason')=?",(reason,)).fetchone()
    if not exists:
        with l.db:l.event('QUANTITATIVE_VALIDATION',{'reason':reason,'originals_modified':False,
          'policy':{'scope':'Actual monthly primary storage migration verification','source_collection':False,'new_numerical_facts':0}})
    proof=private.checkpoint(l,ROOT/'monthly-result');l.close()
    write('monthly-input-proof.json',{'storage':got['storage'],'state':before,'target_proof':proof})
    write('monthly-append-prepared.json',{'already_present':bool(exists),'seconds':time.monotonic()-started})
    print('Monthly append checkpoint prepared seconds='+str(round(time.monotonic()-started,2)),flush=True)


def interrupt():
    started=time.monotonic();m=monthly();got=read('monthly-input-proof.json');exists=read('monthly-append-prepared.json')['already_present']
    if not exists:
        try:m.publish(ROOT/'monthly-result',got['storage'],interrupt_before_commit=True)
        except ValueError as exc:
            if str(exc)!='ARCHIVE_TEST_INTERRUPTED_BEFORE_COMMIT':raise
        else:raise ValueError('MONTHLY_INTERRUPT_NOT_TRIGGERED')
        assert m.head()==got['storage']
    write('monthly-interrupted.json',{'incomplete_generation_not_committed':not bool(exists),
                                    'actual_own_validation_event_added':not bool(exists),'seconds':time.monotonic()-started})
    print('Monthly interrupted publish verified seconds='+str(round(time.monotonic()-started,2)),flush=True)


def resume():
    m=monthly();input=read('monthly-input-proof.json');before=len(m.store().assets())
    result=m.publish(ROOT/'monthly-result',input['storage'])
    after=len(m.store().assets())
    expected_new=0 if result.get('unchanged')else 1
    assert after-before==expected_new  # Data already uploaded before interruption.
    write('monthly-write.json',{'saved':result,'new_objects_on_resume':after-before,'lost_ack_retry':None,
                               'prior_data_object_reused':True})
    print('New research state committed without Git DB write',flush=True)


def duplicate():
    m=monthly();input=read('monthly-input-proof.json');before=len(m.store().assets())
    lost=m.publish(ROOT/'monthly-result',input['storage'])
    assert lost['unchanged'] and len(m.store().assets())==before
    result=read('monthly-write.json');result['lost_ack_retry']=lost;write('monthly-write.json',result)
    print('Repeated/lost-ack save adds no objects',flush=True)


def read_current(args):
    m=monthly()
    if args.corrupt:
        factory=m.factory
        def damaged_factory(*a,**kw):
            obj=factory(*a,**kw);old=obj.read
            def damaged(asset):
                raw=old(asset)
                return raw[:-1]+bytes([raw[-1]^1])if asset['name'].startswith('blob-')else raw
            obj.read=damaged;return obj
        m.factory=damaged_factory
    got=m.receive(ROOT/args.dest);private.restore(ROOT/args.dest,ROOT/(args.dest+'-ledger'))
    l=Ledger(ROOT/(args.dest+'-ledger'));before=file_sha(l.path)
    restored_state=state(l.db);expected=read('monthly-input-proof.json')
    assert restored_state==expected['state']
    packet=json.loads(Path('docs/v4/quantitative/relation-tasks.json').read_text())
    assert counterpart.save_relations(l,packet)['added']==0
    assert file_sha(l.path)==before
    pages=[json.loads(p)for p, in l.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_PAGE_COMMITTED' LIMIT 3")]
    cursors={r['task']:q.cursor(l,r['task'])for r in pages};l.close()
    print(json.dumps({'storage':got['storage'],'verified':got['verified'],'processing_state':restored_state,
                      'existing_relation_additions':0,'dedup_DB_hash_unchanged':True,'sample_resumed_page_cursors':cursors}))


def verify():
    def child(dest,corrupt=False):
        cmd=[sys.executable,__file__,'read-current','--dest',dest]+(['--corrupt']if corrupt else[])
        return subprocess.run(cmd,capture_output=True,text=True,timeout=115)
    bad=child('monthly-corrupt',True)
    assert bad.returncode and 'ARCHIVE_CIPHERTEXT_HASH'in bad.stderr and not(ROOT/'monthly-corrupt').exists()
    good=child('monthly-new-process')
    if good.returncode:raise ValueError('MONTHLY_NEW_PROCESS_FAILED:'+good.stderr[-1000:])
    got=json.loads(good.stdout);assert got['storage']['sqlite_sha256']==read('monthly-input-proof.json')['target_proof']['sqlite_sha256']
    write('monthly-verified.json',{'new_process':got,'corrupted_download_refused':True,'clean_redownload_recovered':True,
                                 'remote_asset_itself_not_modified':True})
    print('Monthly remote restore preserved all page cursors/task history; restart dedup0; corrupt download refused/recovered')


def rollover():
    # Isolated, synthetic dates/records; never presented as actual next-month operation.
    root=ROOT/'rollover';l=Ledger(root/'ledger');raw=root/'test.json';raw.write_text('{"value":12}')
    meta={'url':'https://api.usaspending.gov/api/v2/transactions/','source_id':'usaspending','path':str(raw),
          'sha256':file_sha(raw),'acquired_at':'2026-10-16','published_at':'UNKNOWN'}
    row=q.observation(meta,'synthetic-monthly-test','test','value','12','USD','MONEY','2026-09-01',{'format':'JSON','path':['value']})
    q.commit_page(l,'synthetic-page',meta,[row]);proof=private.checkpoint(l,root/'oct')
    oct=monthly(at=datetime(2026,10,16,tzinfo=timezone.utc),trial=os.environ['GITHUB_RUN_ID'])
    seed={'backend':'git-seed','legacy_parent':oct.anchor,'sqlite_sha256':proof['sqlite_sha256']}
    first=oct.publish(root/'oct',seed)
    with l.db:l.event('QUANTITATIVE_VALIDATION',{'reason':'Synthetic next-month storage test only','originals_modified':False})
    private.checkpoint(l,root/'nov');l.close()
    nov=monthly(at=datetime(2026,11,1,tzinfo=timezone.utc),trial=os.environ['GITHUB_RUN_ID'])
    second=nov.publish(root/'nov',first['storage']);got=nov.receive(root/'reloaded')
    assert second['kind']=='CHECKPOINT' and second['patches']==0 and got['verified']['tables']==8
    write('monthly-rollover.json',{'mode':'SYNTHETIC_DATE_ROLLOVER_NOT_ACTUAL_NOVEMBER','previous':first,'next':second,
                                  'next_month_full_restore':got['verified']})
    print('Separate synthetic October-to-November release rollover and full restore passed')


def finish():
    before=read('before.json');after=inventory()
    assert before['history_unique_object_bytes']==after['history_unique_object_bytes']
    assert all(after['refs'].get(k)==v for k,v in before['refs'].items())
    newrefs=set(after['refs'])-set(before['refs']);assert all(x.startswith('refs/tags/bct-v4-archive-monthly-')for x in newrefs)
    m=monthly();assets=m.store().assets()
    result=stamp_export({'plan_id':'BCT-V4-Q-1.0','run':os.environ['GITHUB_RUN_ID'],'code_SHA':os.environ['GITHUB_SHA'],
       'seed':read('monthly-seed.json'),'interruption':read('monthly-interrupted.json'),'save':read('monthly-write.json'),
       'restore':read('monthly-verified.json'),'rollover':read('monthly-rollover.json'),
       'legacy_parent':m.anchor,'legacy_Git_bytes_before':before['history_unique_object_bytes'],
       'legacy_Git_bytes_after':after['history_unique_object_bytes'],'monthly_assets':assets,
       'monthly_encrypted_bytes':sum(a['size']for a in assets),'free_guard':read('free.json'),
       'new_AI_CPU_source_calls':0,'scheduled_execution':'NOT_RUN','existing_main_CPU_RSS_UI_changed':False,
       'selector_at_trial':ms.policy()['backend']})
    # Do not emit signed URLs or arbitrary API responses from asset metadata.
    result['monthly_assets']=[{k:a[k]for k in ['id','name','size']}for a in assets]
    write('monthly-results.json',result);print('BCT_MONTHLY_STORAGE_JSON='+json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','seed','append','interrupt','resume','duplicate','verify','rollover','finish','read-current'])
    p.add_argument('--dest');p.add_argument('--corrupt',action='store_true');args=p.parse_args()
    if args.action=='read-current':read_current(args)
    else:globals()[args.action]()
