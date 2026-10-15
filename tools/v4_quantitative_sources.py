"""Restore only missing frozen official source versions, never overwrite a vintage.

No schedules, AI/CPU work, authentication probing, article collection or secret
setting changes. A newer file at the same URL is retained separately and held.
"""
import json,re,time,argparse
from pathlib import Path
from bct.v4.adapters import SourceClient
from bct.v4.store import sha,now
ROOT=Path('var/v4/quantitative/q1/discovery')


def prepare(source):
    spec=json.loads(Path('docs/v4/quantitative/source-registry.json').read_text());start=time.monotonic();result=[];requests=0
    for task in spec['file_tasks']:
        if task['source_id']!=source:continue
        key=task['key']
        if not re.fullmatch('[a-z0-9-]+',key):raise ValueError('INVALID_CACHE_KEY')
        path=ROOT/(key+'.raw');proof=path.with_suffix('.json')
        mismatch=proof.with_suffix('.version-held')
        if mismatch.exists():
            result.append({'task':key,'status':'HELD_NEW_VERSION_NO_REPEAT_DOWNLOAD'});continue
        if path.exists():
            if sha(path.read_bytes())!=task['sha256']:raise ValueError('EXISTING_FROZEN_SOURCE_HASH_MISMATCH')
            result.append({'task':key,'status':'EXACT_CACHED_VERSION_REUSED'});continue
        if proof.exists()and json.loads(proof.read_text()).get('status')not in (200,):
            result.append({'task':key,'status':'HELD_PREVIOUS_FAILURE_NO_RETRY'});continue
        if requests>=32 or time.monotonic()-start>95:
            result.append({'task':key,'status':'BATCH_BUDGET_RESUME_REQUIRED'});break
        try:
            requests+=1;raw,url,status,mime=SourceClient().fetch(task['url']);digest=sha(raw)
            if digest!=task['sha256']:
                versions=ROOT/'unfrozen-versions';versions.mkdir(parents=True,exist_ok=True)
                new=versions/(digest+'.raw')
                if not new.exists():new.write_bytes(raw);new.chmod(0o600)
                mismatch.write_text(json.dumps({'expected':task['sha256'],'received':digest,'no_repeat_download':True,'acquired_at':now()}))
                result.append({'task':key,'status':'NEW_VERSION_HELD_NOT_REPLACED','received_hash':digest});continue
            ROOT.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o600)
            m=json.loads(proof.read_text())if proof.exists()else{}
            m={**m,'url':task['url'],'source_id':source,'status':status,'sha256':digest,'bytes':len(raw),'acquired_at':m.get('acquired_at',task.get('acquired_at',now())),'restored_at':now(),'content_type':mime}
            proof.write_text(json.dumps(m,indent=2)+'\n');result.append({'task':key,'status':'EXACT_VERSION_RESTORED'})
        except Exception as e:
            status=getattr(e,'code','FAILED');proof.parent.mkdir(parents=True,exist_ok=True)
            proof.write_text(json.dumps({'url':task['url'],'status':status,'reason':type(e).__name__,'same_request_retry_allowed':False})+'\n')
            result.append({'task':key,'status':'BLOCKED','HTTP':status})
    return {'source':source,'requests':requests,'results':result}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',choices=['m3','g17','eia','usgs']);a=p.parse_args();print(json.dumps(prepare(a.source)))
