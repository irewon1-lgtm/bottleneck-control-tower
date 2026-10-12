"""Real failed source and pinned CPU model, before/after extent grammar."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import urlopen
from typing import Any
from bct.future_github import GitHubTransport
from bct.future_local_reader import LocalCPUQuickReader, native_schema
from bct.future_worker import _runs
from bct.recovery_preservation import digest
from bct_local_reader_probe import setup


def main():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-native-extent-probe';root.mkdir(exist_ok=True)
    old=Path(os.environ['RUNNER_TEMP'])/'failed-native'
    document_id='116b03c5-3113-4364-8627-560de623e592'
    body_sha='a435f2a8a0c0a6f5e6ffb6ddb27c22764e96d4072cbc6637e3fd95480707332a'
    c=json.loads((old/'future-output/future-candidates.json').read_text())
    body=(old/'automatic-local-reader/private-source-cache'/(body_sha+'.txt')).read_text()
    assert len(body)==5535 and hashlib.sha256(body.encode()).hexdigest()==body_sha
    payload={'document_id':document_id,'title':c['results'][document_id].get('title'),
             'body_sha256':body_sha,'body_status':'FULL','read_start':5534,
             'expected_read_end':5535,'body':body}
    transport=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
    head=transport.head();tracking=transport.read_at('future-tracking.json',head)
    errors=[v for v in _runs(tracking.document).values() if v.get('document_id')==document_id
            and v.get('body_sha256')==body_sha and v.get('state')=='ERROR'
            and v.get('run_id')=='quick-worker-5f1a37110f1d4e41b9ada9134fda9ac3']
    assert len(errors)==1 and errors[0]['reason']=='HTTPError' and errors[0]['read_start']==5534
    before_source,blob=transport._root('src/bct/future_local_reader.py','367bf477717561380282d1b9f5ca46fc82f11323')
    path=root/'baseline.py';path.write_bytes(before_source)
    spec=importlib.util.spec_from_file_location('bct.extent_baseline',path)
    if spec is None or spec.loader is None:
        raise RuntimeError('baseline reader module unavailable')
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    old_range=baseline.native_schema(payload)['oneOf'][1]['properties']['read_end']
    assert old_range['minimum']>old_range['maximum']
    proof={'run_id':os.environ['GITHUB_RUN_ID'],'code_sha':os.environ['GITHUB_SHA'],
           'status':'FAIL','actual_native_execution':True,'production_ref_writes':0,
           'source_body_sha256':body_sha,'document_id':document_id,'read_start':5534,'expected_read_end':5535,
           'original_stopped_error':errors[0],'original_error_sha256':digest(errors[0]),
           'original_tracking_commit':head,'baseline_git_blob':blob,'invalid_before_range':old_range,
           'corrected_schema':native_schema(payload),'prediction_performance':'UNVERIFIED'}
    binary,weight,verified=setup(root,json.loads(Path('config/bct-local-reader.json').read_text()))
    process=None
    try:
        with (root/'native-server.log').open('w') as log:
            process=subprocess.Popen([str(binary),'-m',str(weight),'--alias',verified['alias'],
                '--host','127.0.0.1','--port','8080','-c',str(verified['context_tokens']),
                '-t','4','-tb','4','-np','1','--no-context-shift','--log-disable'],stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+120
            while True:
                if process.poll() is not None:raise RuntimeError('native server exited')
                try:
                    with urlopen('http://127.0.0.1:8080/health',timeout=2) as r:
                        if r.status==200:break
                except OSError:
                    if time.monotonic()>=deadline:raise TimeoutError('native startup')
                    time.sleep(1)
            try:
                baseline.LocalCPUQuickReader(verified,timeout=600)(payload)
            except HTTPError as exc:
                raw=exc.read(1000000);(root/'private-before-http-error.json').write_bytes(raw)
                proof['before']={'status':'FAIL','error_type':'HTTPError','http_status':exc.code,
                                 'response_sha256':hashlib.sha256(raw).hexdigest()}
            else:raise ValueError('baseline did not reproduce original failure')
            observations: list[dict[str,Any]]=[]
            result=LocalCPUQuickReader(verified,timeout=600,receipt_observer=observations.append)(payload)
            assert result['review']['read_end']==5535 and result['review']['disposition']!='INCOMPLETE'
            assert len(observations)==1 and observations[0]['truncated'] is False
            proof['after']={'status':'PASS','actual_response':result,'native_receipt':observations[0]}
            proof['status']='PASS'
    finally:
        if process is not None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        (root/'extent-probe.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(json.dumps({k:proof[k] for k in ('run_id','status','production_ref_writes','invalid_before_range')}))


if __name__=='__main__':main()
