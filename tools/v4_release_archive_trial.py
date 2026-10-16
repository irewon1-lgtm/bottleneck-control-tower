"""Manual, private Releases validation. No primary writer/scheduler selection."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from bct.v4 import release_archive as archive, quantitative_private as private
from bct.v4 import private_state, quantitative as q, cpu_operations
from bct.v4.store import Ledger, file_sha
from bct.objective_lock import stamp_export

ROOT = Path('var/v4/storage-archive/trial')


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2))


def password():
    value = os.environ.get('BCT_V4_STATE_PASSPHRASE', '')
    if not 40 <= len(value) <= 256:
        raise ValueError('EXISTING_ARCHIVE_SECRET_NOT_DELIVERED')
    return value


def git(*args):
    token = os.environ['BCT_V4_PRIVATE_STATE_TOKEN']
    auth = base64.b64encode(('x-access-token:' + token).encode()).decode()
    env = {**os.environ, 'GIT_CONFIG_COUNT':'2', 'GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader',
           'GIT_CONFIG_VALUE_0':'AUTHORIZATION: basic ' + auth, 'GIT_CONFIG_KEY_1':'credential.helper',
           'GIT_CONFIG_VALUE_1':'', 'GIT_TERMINAL_PROMPT':'0'}
    p = subprocess.run(['git','-C',str(ROOT/'legacy-read'),*args],capture_output=True,env=env,timeout=25)
    if p.returncode:
        raise ValueError('ARCHIVE_LEGACY_READ_FAILED')
    return p.stdout


def inventory():
    git('fetch','--no-tags','origin','+refs/heads/*:refs/remotes/origin/*','+refs/tags/*:refs/tags/*')
    refs = git('for-each-ref','--format=%(refname) %(objectname)','refs/remotes/origin','refs/tags').decode().splitlines()
    objects = git('rev-list','--objects','--all').decode().splitlines()
    # Supplying object IDs through stdin keeps credentials out of command arguments.
    # cat-file is local and needs no authentication at all.
    result = subprocess.run(['git','-C',str(ROOT/'legacy-read'),'cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                            input=('\n'.join(x.split()[0] for x in objects)+'\n').encode(),capture_output=True,check=True,timeout=25)
    total = sum(int(x.split()[2]) for x in result.stdout.decode().splitlines())
    return {'refs':dict(x.split() for x in refs),'history_unique_object_bytes':total}


def store(kind):
    config = read('legacy.json')
    return archive.Releases(os.environ['BCT_V4_PRIVATE_STATE_TOKEN'],
                            'bct-v4-archive-' + kind + '-' + os.environ['GITHUB_RUN_ID'], config['parent']).ensure()


def child(*args, expected_failure=False):
    p = subprocess.run([sys.executable,__file__,*args],capture_output=True,text=True,timeout=115)
    if expected_failure:
        if p.returncode == 0 or 'ARCHIVE_CIPHERTEXT_HASH' not in p.stderr:
            raise ValueError('ARCHIVE_CORRUPTION_NOT_REFUSED')
        return {'corrupt_download_rejected':True,'new_destination_not_committed':True}
    if p.returncode:
        raise ValueError('ARCHIVE_CHILD_FAILED:' + p.stderr[-1200:])
    return json.loads(p.stdout)


def prepare():
    ROOT.mkdir(parents=True,exist_ok=True)
    write('free.json',cpu_operations.github_guard())
    legacy = private.remote_checkpoint(ROOT/'legacy-read',ROOT/'legacy-checkpoint',os.environ['BCT_V4_PRIVATE_STATE_TOKEN'])
    write('legacy.json',legacy); write('before.json',inventory())
    print('Audited existing facts restored for shadow backup; no Git write or CPU execution')


def synthetic():
    ledger = Ledger(ROOT/'synthetic-ledger');raw=ROOT/'synthetic.json';raw.write_text('{"value":12}')
    m={'url':'https://api.usaspending.gov/api/v2/transactions/','source_id':'usaspending',
       'path':str(raw),'sha256':file_sha(raw),'acquired_at':'2026-10-16','published_at':'UNKNOWN'}
    row=q.observation(m,'synthetic-contract','synthetic-class','transaction_obligation','12','USD','MONEY','2026-09-01',{'format':'JSON','path':['value']})
    q.commit_page(ledger,'synthetic-page',m,[row])
    proofs=[]
    for n in range(3):
        if n:
            with ledger.db:ledger.event('QUANTITATIVE_VALIDATION',{'reason':f'Non-sensitive test revision {n}','originals_modified':False})
        proofs.append(private.checkpoint(ledger,ROOT/f'synthetic-{n}'))
    ledger.close();write('synthetic-proofs.json',proofs)
    s=store('test');p=password()
    first=archive.publish(s,ROOT/'synthetic-0',p,expected_generation=-1)
    before=len(s.assets());same=archive.publish(s,ROOT/'synthetic-0',p,expected_generation=0)
    assert len(s.assets())==before
    try:archive.publish(s,ROOT/'synthetic-1',p,expected_generation=0,interrupt_before_commit=True)
    except ValueError as exc:
        if str(exc)!='ARCHIVE_TEST_INTERRUPTED_BEFORE_COMMIT':raise
    else:raise ValueError('ARCHIVE_INTERRUPTION_NOT_TRIGGERED')
    assert archive.generations(s)==[0]
    write('synthetic-initial.json',{'first':first,'unchanged':same,'before_recovery_assets':len(s.assets()),'incomplete_generation_not_visible':True})
    print('Non-sensitive full upload/download, no-op dedup and interrupted publication verified')


def recover():
    s=store('test');p=password();before=len(s.assets())
    resumed=archive.publish(s,ROOT/'synthetic-1',p,expected_generation=0,max_deltas=1)
    assert len(s.assets())==before+1  # Only commit, no repeated data object.
    checkpoint=archive.publish(s,ROOT/'synthetic-2',p,expected_generation=1,max_deltas=1)
    write('synthetic-recovery.json',{'resumed':resumed,'reused_orphan_no_duplicate_object':True,
                                   'periodic_checkpoint':checkpoint,'short_chain_is_test_only':True,'production_chain_cap':archive.MAX_DELTAS})
    print('Interrupted data object reused, commit completed, periodic checkpoint verified')


def restore_command(args):
    s=store(args.kind)
    if args.corrupt_download:
        original=s.read
        def damaged(asset):
            raw=original(asset)
            return raw[:-1]+bytes([raw[-1]^1]) if asset['name'].startswith('blob-') else raw
        s.read=damaged  # Corrupt downloaded bytes only; remote objects are untouched.
    proof=archive.restore(s,args.generation,password(),ROOT/args.dest,expected_sqlite_sha256=args.expected_hash)
    print(json.dumps(proof))


def verify_synthetic():
    wanted=read('synthetic-proofs.json')
    bad=child('restore','--kind','test','--generation','2','--dest','damaged-download','--expected-hash',wanted[2]['sqlite_sha256'],'--corrupt-download',expected_failure=True)
    assert not(ROOT/'damaged-download').exists()
    final=child('restore','--kind','test','--generation','2','--dest','synthetic-remote-restored','--expected-hash',wanted[2]['sqlite_sha256'])
    prior=child('restore','--kind','test','--generation','0','--dest','synthetic-prior-restored','--expected-hash',wanted[0]['sqlite_sha256'])
    write('synthetic-verified.json',{'failure_injection':'Locally corrupted download of a real remote ciphertext; remote object not modified',
                                  'damage':bad,'correct_remote_redownload_new_process':final,'explicit_old_generation_restore':prior})
    print('Actual remote download corruption refused; new-process clean redownload and explicit prior generation restored')


def shadow():
    s=store('shadow')
    value=archive.publish(s,ROOT/'legacy-checkpoint',password(),expected_generation=-1)
    write('shadow-published.json',value)
    print('Current audited facts shadow archive published; legacy writer unchanged')


def verify_shadow():
    expected=read('legacy.json')['verified']['sqlite_sha256']
    value=child('restore','--kind','shadow','--generation','0','--dest','shadow-remote-restored','--expected-hash',expected)
    assert value['sqlite_sha256']==expected
    assert json.loads((ROOT/'legacy-checkpoint/checkpoint.json').read_text())['tables']==json.loads((ROOT/'shadow-remote-restored/checkpoint.json').read_text())['tables']
    write('shadow-verified.json',{'new_process_remote_restore':value,'all_original_tables_equal':True,
                                'article_originals_not_in_this_capsule':True})
    print('All current fact-state table hashes preserved in remote archive new-process restore')


def rollback():
    # Actual fresh legacy remote read after the new archive: no primary pointer was changed.
    legacy=private.remote_checkpoint(ROOT/'rollback-read',ROOT/'legacy-rollback',os.environ['BCT_V4_PRIVATE_STATE_TOKEN'])
    expected=read('legacy.json');assert legacy['parent']==expected['parent']
    assert legacy['verified']['sqlite_sha256']==expected['verified']['sqlite_sha256']
    before=read('before.json');after=inventory()
    assert before['history_unique_object_bytes']==after['history_unique_object_bytes']
    assert all(after['refs'].get(k)==v for k,v in before['refs'].items())
    extra=set(after['refs'])-set(before['refs'])
    assert all(x.startswith('refs/tags/bct-v4-archive-')for x in extra)
    assets={kind:store(kind).assets()for kind in ['test','shadow']}
    summary=stamp_export({'plan_id':'BCT-V4-Q-1.0','code_SHA':os.environ['GITHUB_SHA'],'run':os.environ['GITHUB_RUN_ID'],
       'non_sensitive_initial':read('synthetic-initial.json'),'non_sensitive_recovery':read('synthetic-recovery.json'),
       'non_sensitive_verification':read('synthetic-verified.json'),'current_facts_shadow':read('shadow-verified.json'),
       'legacy_parent':legacy['parent'],'legacy_rollback_equal':True,'legacy_Git_bytes_before':before['history_unique_object_bytes'],
       'legacy_Git_bytes_after':after['history_unique_object_bytes'],'new_tags_point_to_existing_commit':sorted(extra),
       'archive_assets':{k:[{field:a[field]for field in ['id','name','size']}for a in rows]for k,rows in assets.items()},
       'new_encrypted_asset_bytes':sum(a['size']for rows in assets.values()for a in rows),
       'unchanged_primary_writer':True,'CPU_or_AI_calls':0,'source_collection_requests':0,'new_originals_copied':0,
       'primary_cutover':'NOT_RUN_SEPARATE_APPROVAL','free_guard':read('free.json')})
    write('results.json',summary);print('BCT_ARCHIVE_TRIAL_JSON='+json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','synthetic','recover','verify-synthetic','shadow','verify-shadow','rollback','restore'])
    parser.add_argument('--kind',choices=['test','shadow']);parser.add_argument('--generation',type=int)
    parser.add_argument('--dest');parser.add_argument('--expected-hash');parser.add_argument('--corrupt-download',action='store_true')
    args=parser.parse_args();start=time.monotonic()
    if args.action=='restore':restore_command(args)
    else:globals()[args.action.replace('-','_')]()
