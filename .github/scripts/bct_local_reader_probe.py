"""Read-only real-source CPU pilot; never claims production queue recovery.

Weights and runtime are pinned. A paid model endpoint is never used. Raw
inputs/outputs remain private artifact receipts, not candidate promotions.
"""
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
from urllib.request import urlopen

from bct.future_github import GitHubTransport
from bct.future_local_reader import LocalCPUQuickReader
from bct.future_review import _records, document_complete
from bct.recovery_pilot import resume_batches


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def setup(root,config):
    directory=root/'local-reader-runtime';directory.mkdir(exist_ok=True)
    source=directory/'llama.cpp'
    if not source.exists():
        subprocess.run(['git','clone','--no-checkout','--filter=blob:none',
            'https://github.com/ggml-org/llama.cpp.git',str(source)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','-C',str(source),'checkout','--detach',config['llama_cpp_sha']],check=True,stdout=subprocess.DEVNULL)
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if actual!=config['llama_cpp_sha']:raise ValueError('local runtime build identity mismatch')
    log=root/'local-reader-build.log'
    with log.open('w') as output:
        subprocess.run(['cmake','-S',str(source),'-B',str(source/'build'),
            '-DCMAKE_BUILD_TYPE=Release','-DLLAMA_BUILD_TESTS=OFF','-DGGML_CUDA=OFF'],
            check=True,stdout=output,stderr=subprocess.STDOUT)
        subprocess.run(['cmake','--build',str(source/'build'),'-j','4','--target','llama-server'],
            check=True,stdout=output,stderr=subprocess.STDOUT)
    weights=directory/'weights';weights.mkdir(exist_ok=True)
    verified={}
    for name,expected in config['files'].items():
        path=weights/name
        if not path.exists():
            url='https://huggingface.co/'+config['model']+'/resolve/'+config['revision']+'/'+name
            temporary=path.with_suffix('.partial');size=0
            with urlopen(url,timeout=30) as response,temporary.open('wb') as output:
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>5*1024**3:raise ValueError('weight download exceeds pinned capture bound')
                    output.write(chunk)
            if digest(temporary)!=expected:raise ValueError('downloaded local weight hash mismatch')
            temporary.replace(path)
        if digest(path)!=expected:raise ValueError('cached local weight hash mismatch')
        verified[name]=expected
    receipt={**config,'files':verified,'weights_verified':True,'build_verified':True,
             'verified_at':datetime.now(timezone.utc).isoformat()}
    (root/'local-reader-setup.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return source/'build/bin/llama-server',weights/next(iter(config['files'])),receipt


def main():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    prior=json.loads((root/'checkpoint.json').read_text())
    if any(prior.get('gate'+str(i))!='PASS' for i in range(5)):
        raise RuntimeError('official evidence audit must pass before reading pilot')
    config=json.loads(Path('config/bct-local-reader.json').read_text())
    # Repository billing intent is explicit: never select paid/private runners.
    if os.environ.get('BCT_PUBLIC_REPOSITORY')!='true':
        raise RuntimeError('standard public repository runner required')
    report: dict[str, Any]={'run_id':os.environ['GITHUB_RUN_ID'],'code_sha':os.environ['GITHUB_SHA'],
            'status':'BLOCKED','gate5':'BLOCKED','full_clean_status':'BLOCKED',
            'reason':'PRODUCTION_QUEUE_RECOVERY_NOT_YET_CONNECTED',
            'api_cost_usd':0,'production_completions_added':0,'batches':[],
            'model_calls_this_run':0,
            'prediction_performance':'UNVERIFIED','live_early':0}
    process=None
    try:
        binary,weight,receipt=setup(root,config)
        server_log=(root/'local-reader-server.log').open('w')
        process=subprocess.Popen([str(binary),'-m',str(weight),'--alias',config['alias'],
            '--host','127.0.0.1','--port','8080','-c',str(config['context_tokens']),
            '-t','4','-tb','4','-np','1','--no-context-shift','--log-disable'],
            stdout=server_log,stderr=subprocess.STDOUT)
        ready=time.monotonic()+120
        while True:
            if process.poll() is not None:raise RuntimeError('local reader server exited')
            try:
                with urlopen('http://127.0.0.1:8080/health',timeout=2) as response:
                    if response.status==200:break
            except OSError:
                if time.monotonic()>=ready:raise TimeoutError('local reader startup deadline')
                time.sleep(1)
        transport=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
        candidates=transport.read('future-candidates.json');tracking=transport.read('future-tracking.json')
        version_map={(x['document_id'],x['body_sha256']):x for x in _records(candidates.document)}
        versions=json.loads((root/'source-recovery-versions.json').read_text())
        def observe_inference(value):
            value.update(run_id=report['run_id'],observed_at=datetime.now(timezone.utc).isoformat())
            with (root/'private-local-reader-execution.jsonl').open('a') as journal:
                journal.write(json.dumps(value,ensure_ascii=False)+'\n');journal.flush();os.fsync(journal.fileno())
            report['returned_inferences_this_run']=report.get('returned_inferences_this_run',0)+1
        recovered={(v['document_id'],v['old_body_sha256']) for v in versions if v['exact_version_recovered']}
        observations={x['url']:x for x in map(json.loads,(root/'source-recovery-attempts.jsonl').read_text().splitlines())}
        reader=LocalCPUQuickReader(receipt,receipt_observer=observe_inference);items=[]
        for key,item in version_map.items():
            observation=observations.get(item.get('url'),{})
            new_observed=(item.get('source_recovery') and observation.get('body_status')=='FULL'
                          and observation.get('body_sha256')==key[1])
            if (key not in recovered and not new_observed or item['body_status']!='FULL'
                    or document_complete(tracking.document,item)):continue
            body=(root/'private-source-cache'/(key[1]+'.txt')).read_text()
            if hashlib.sha256(body.encode()).hexdigest()!=key[1] or len(body)!=item['body_chars']:
                raise ValueError('real pilot source identity/extent mismatch')
            payload={'document_id':key[0],'title':item.get('title'),'body_sha256':key[1],
                'body_status':'FULL','read_start':0,'expected_read_end':len(body),'body':body}
            if reader.input_characters(payload)<=12000:items.append(payload)
        items.sort(key=lambda x:(len(x['body']),x['document_id']))
        report.update(candidate_blob_sha=candidates.sha,tracking_blob_sha=tracking.sha,
                      eligible_real_sources=len(items),model_setup_receipt=receipt)
        previous_path=Path(os.environ['RUNNER_TEMP'])/'bct-recovery-resume/local-reader-probe.json'
        previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
        previous_checkpoint=previous_path.parent/'checkpoint.json'
        already_applied=(previous_checkpoint.exists() and json.loads(previous_checkpoint.read_text()).get('gate5')=='PASS')
        qualification=(previous.get('qualification_pilot') if previous.get('mode')=='DRAIN'
                       else previous if already_applied else None)
        qualified=bool(qualification and qualification.get('probe_status')=='PASS'
                       and [b.get('limit') for b in qualification.get('batches',[])]==[1,10,50])
        report['mode']='DRAIN' if qualified else 'QUALIFICATION'
        limits: tuple[int,...]
        if qualified:
            report['qualification_pilot']=deepcopy(qualification)
            limits=(min(50,len(items)),) if items else ()
        else:
            if len(items)<61:raise RuntimeError('61 distinct recovered FULL unread pilot documents unavailable')
            limits=(1,10,50)
        report['batch_limits']=list(limits)
        report['batches']=resume_batches(previous,items,config,limits=limits) if not already_applied else []
        report['prior_pilot_already_applied']=already_applied
        report['prior_model_calls_restored']=sum(len(b['results']) for b in report['batches'])
        if previous:
            report['previous_pilot_checkpoint_sha256']=hashlib.sha256(previous_path.read_bytes()).hexdigest()
            report['previous_pilot_run_id']=previous['run_id']
        offset=0;deadline=time.monotonic()+30*60
        for index,count in enumerate(limits):
            if index<len(report['batches']):batch=report['batches'][index]
            else:
                batch={'limit':count,'actual_model_calls':0,'results':[],'status':'RUNNING'}
                report['batches'].append(batch)
            for payload in items[offset+len(batch['results']):offset+count]:
                if time.monotonic()>=deadline:
                    report['reason']='RUNNER_DEADLINE';return 1
                response=reader(payload)
                report['model_calls_this_run']+=1
                batch['actual_model_calls']+=1
                if response['review']['disposition']=='INCOMPLETE':raise RuntimeError('real local pilot reading incomplete')
                # Identity, range and real token counters are retained. The
                # private source itself remains in the hash-verified cache.
                batch['results'].append({**response,'document_id':payload['document_id'],
                    'body_sha256':payload['body_sha256'],'read_start':0,
                    'actual_execution_run_id':report['run_id'],
                    'expected_read_end':payload['expected_read_end']})
                (root/'local-reader-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            batch['status']='PASS';offset+=count
        report.update(probe_status='PASS',actual_model_calls=sum(limits),
                      next_requirement='Apply actual readings with immutable bindings and verify production 7-state queue before Gate 5 PASS')
    except Exception as exc:
        report.update(probe_status='FAIL',error_type=type(exc).__name__,
                      reason='LOCAL_READER_PROBE_'+type(exc).__name__,
                      resume_condition='Fix the recorded local setup/inference failure; restart Stage 0')
        if type(exc) in (ValueError,RuntimeError,TimeoutError):report['failure_code']=str(exc)
        # Avoid provider responses containing article text in public logs.
    finally:
        if process is not None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        (root/'local-reader-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('status','gate5','probe_status','reason','actual_model_calls','api_cost_usd')}))
    return 0 if report.get('probe_status')=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
