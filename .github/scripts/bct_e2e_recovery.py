"""Gate 6 executes actual source traces and required regression commands.

Missing proof, failing quality checks and required test skips cannot become PASS.
No prediction/score/confirmed TARGET writes are performed by this executor.
"""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from typing import Any

from bct.future_github import GitHubTransport,_raw
from bct.future_review import _records,document_complete
from bct.recovery_preservation import verify
from bct.recovery_queue import project
from bct.recovery_e2e import trace_source,verify_display_generation,confirmed_full_observation

FROZEN={'precursor_discovery.py':'614e841938daf41e34d7e31b97ec636f06f2997c8b7b4252926dd135e5bc2639',
    'early_forecast.py':'51d90d2265baec516d20383579816c5155e46c69599a8e7b281d329843d17675',
    'forecast_discovery.py':'5a491f55f14a3fef675c0ca652042bb1cd8b76cb0de40c6f003d55181e2480fd',
    'prospective.py':'6ca939e378ffb02323feecb869aa1aac0e9f7b56ec5cbc92689233e30d65a153'}


def quality(root):
    checked=sorted([str(p) for p in Path('src/bct').glob('recovery_*.py')])
    checked+=['src/bct/future_local_reader.py','src/bct/future_github.py','src/bct/future_ui.py']
    checked+=['src/bct/future_store.py','src/bct/future_body.py','src/bct/future_review.py',
        'src/bct/future_hypothesis.py','src/bct/future_reader.py','src/bct/future_worker.py',
        'src/bct/future_bottleneck.py','src/bct/future_quality.py']
    checked+=sorted(str(p) for p in Path('.github/scripts').glob('bct_*recovery.py'))
    commands=[('python',[sys.executable,'-m','pytest','-q','--junitxml='+str(root/'e2e-python.xml')]),
        ('javascript',['node','--test',*sorted(str(p) for p in Path('tests').glob('*.js'))]),
        ('lint',[sys.executable,'-m','ruff','check','--select','F','src','.github/scripts']),
        ('syntax',[sys.executable,'-m','compileall','-q','src','.github/scripts']),
        ('typed_recovery_interfaces',[sys.executable,'-m','mypy','--follow-imports','skip',
            '--check-untyped-defs','--cache-dir',str(root/'mypy-cache'),*checked]),
        ('build',[sys.executable,'-m','build','--wheel','--outdir',str(root/'built-wheel')]),
        ('original_230_wrapper',[sys.executable,'tools/precursor_operating_qa.py',
            '--cache',str(root/'fixed-precursor-qa'),'--output',str(root/'e2e-original-230/operating-report.json')])]
    receipts: list[dict[str,Any]]=[]
    for name,args in commands:
        log=root/('e2e-'+name+'.log');started=datetime.now(timezone.utc).isoformat()
        with log.open('w') as stream:
            code=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,check=False,
                env={**os.environ,'MYPYPATH':str(Path('src').resolve())}).returncode
        receipts.append({'check':name,'status':'PASS' if code==0 else 'FAIL','exit_code':code,
            'execution_id':os.environ['GITHUB_RUN_ID']+'-'+name+'-'+uuid.uuid4().hex,
            'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
            'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'log_file':log.name})
    skipped=[]
    for case in ET.parse(root/'e2e-python.xml').getroot().iter('testcase'):
        entry=case.find('skipped')
        if entry is None:continue
        reason=entry.get('message','')
        allowed=(case.get('classname')=='tests.test_forecast_discovery'
            and case.get('name')=='test_D_real_pre_public_holdout'
            and reason=='BLOCKED: independent frozen real pre-public holdout and archived precursor facts unavailable')
        skipped.append({'test':str(case.get('classname'))+'.'+str(case.get('name')),
            'reason':reason,'prediction_only_external_blocker':allowed})
    if any(not s['prediction_only_external_blocker'] for s in skipped):
        receipts.append({'check':'required_test_skip','status':'FAIL','skips':skipped})
    return {'checks':receipts,'skipped_tests':skipped,'typecheck_scope':checked,
        'typescript':'NOT_APPLICABLE_NO_TS_SOURCES' if not list(Path('src').rglob('*.ts')) else 'BLOCKED_TS_CHECK_MISSING',
        'prediction_performance':'UNVERIFIED'}


def execute():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    checkpoint=root/'checkpoint.json';report=json.loads(checkpoint.read_text())
    if any(report.get('gate'+str(i))!='PASS' for i in range(6)):
        raise RuntimeError('operating Gates 0 through 5 required before E2E')
    proof: dict[str,Any]={'run_id':os.environ['GITHUB_RUN_ID'],'code_sha':os.environ['GITHUB_SHA'],
        'execution_id':uuid.uuid4().hex,'status':'FAIL','production_decisions_written':0,
        'prediction_performance':'UNVERIFIED','live_early':0}
    try:
        hashes={name:hashlib.sha256((Path('src/bct')/name).read_bytes()).hexdigest() for name in FROZEN}
        if hashes!=FROZEN:raise ValueError('frozen prediction engine raw hashes changed')
        proof['frozen_engine_hashes']=hashes
        transport=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
        c=transport.read('future-candidates.json');t=transport.read('future-tracking.json')
        verify(c.document,t.document,json.loads(Path('config/bct-recovery-preservation.json').read_text()))
        retained=json.loads((root/'recovery-preservation-seal.json').read_text())
        verify(c.document,t.document,retained)
        versions=json.loads((root/'source-recovery-versions.json').read_text())
        observations={x['url']:x for x in map(json.loads,(root/'source-recovery-attempts.jsonl').read_text().splitlines())}
        queue=project(c.document,t.document,versions,observations,root/'private-source-cache')
        saved=c.document['summary']['recovery_queue']
        if saved['counts']!=queue['counts'] or queue['completion_failure_state_overlap']!=0:
            raise ValueError('stored operating queue differs from actual version partition')
        records={(x['document_id'],x['body_sha256']):x for x in _records(c.document)}
        pilot=json.loads((root/'local-reader-probe.json').read_text())
        imported=[]
        for batch in pilot['batches']:
            for reading in batch['results']:
                item=records[(reading['document_id'],reading['body_sha256'])]
                if not document_complete(t.document,item):raise ValueError('actual quick read missing after publication')
                imported.append((item['document_id'],item['body_sha256']))
        traces=[];roles: Counter[str]=Counter()
        for key,item in records.items():
            observation=observations.get(item.get('url'),{})
            path=root/'private-source-cache'/(key[1]+'.txt')
            if not confirmed_full_observation(item,observation) or not path.exists():continue
            trace=trace_source(item,path.read_text(),t.document)
            if key in imported or trace['facts']:
                traces.append(trace);roles.update(f['role'] for f in trace['facts'])
        if imported and not set(imported)<={(x['document_id'],x['body_sha256']) for x in traces}:
            raise ValueError('actual imported reading missing from same-source E2E')
        if not traces or not roles.get('DEMAND') or not roles.get('SUPPLY') or not roles.get('RELIEF'):
            raise ValueError('real source demand supply relief parser integration not exercised')
        proof.update(actual_source_traces=traces,actual_role_counts=dict(roles),
            production_readings_verified=len(imported),queue_partition=queue['counts'],
            history_preservation='PASS',source_binding_checks='PASS',
            target_linking_validation='SOURCE_LOCATORS_AND_EXISTING_NEGATIVE_REGRESSION_ONLY',
            semantic_target_accuracy='UNVERIFIED_WITHOUT_GOLDEN',
            display=[verify_display_generation(path,s.document,hashlib.sha256(_raw(s.document)).hexdigest())
                     for path,s in (('future-candidates.json',c),('future-tracking.json',t))])
        proof['regression']=quality(root)
        if any(x['status']!='PASS' for x in proof['regression']['checks']):
            raise RuntimeError('required regression or quality check failed; see e2e logs')
        if proof['regression']['typescript'].startswith('BLOCKED'):raise RuntimeError('required TypeScript check missing')
        # Read again after all checks. A changed generation needs another Stage 0.
        if transport.read('future-candidates.json').sha!=c.sha or transport.read('future-tracking.json').sha!=t.sha:
            raise RuntimeError('generation changed during independent E2E validation')
        proof['status']='PASS'
        report.update(stage=6,status='PASS',gate6='PASS',next_stage=7,
            e2e_execution_id=proof['execution_id'],full_clean_status='BLOCKED',
            full_clean_reason='OPERATING_PUBLICATION_STAGE_7_AND_FULL_REQUIRED')
        return 0
    except Exception as exc:
        proof.update(error_type=type(exc).__name__)
        if type(exc) in (ValueError,RuntimeError):proof['failure_code']=str(exc)
        report.update(stage=6,status='FAIL',gate6='FAIL',next_stage=0,
            full_clean_status='BLOCKED',resume_condition='Fix recorded E2E/quality issue; restart Stage 0')
        return 1
    finally:
        proof['finished_at']=datetime.now(timezone.utc).isoformat()
        (root/'e2e-recovery.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
        report['e2e_proof_sha256']=hashlib.sha256((root/'e2e-recovery.json').read_bytes()).hexdigest()
        checkpoint.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('stage','status','gate6','full_clean_status')}))


if __name__=='__main__':raise SystemExit(execute())
