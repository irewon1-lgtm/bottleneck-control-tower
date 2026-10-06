"""Read-only SHADOW observer and unactivated evaluation sidecars. No intake calls."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

REPO = 'irewon1-lgtm/bottleneck-control-tower'
STATE_REF = 'refs/heads/review-lead-evaluation-state'
UNKNOWN = 'UNKNOWN'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def metric(value, source, window, unit='documents', status=None):
    return dict(value=value, status=status or ('UNKNOWN' if value == UNKNOWN else 'OBSERVED'),
                source=source, window=window, unit=unit)


def api(path):
    p = subprocess.run(['gh', 'api', f'repos/{REPO}/'+path], capture_output=True)
    if p.returncode:
        # No signed redirect URLs, credential material or arbitrary upstream messages.
        return {'access':'BLOCKED', 'reason':'API_REQUEST_FAILED', 'http_status':
                next((n for n in (403,404,401) if str(n).encode() in p.stderr), UNKNOWN)}
    return {'access':'PASS', 'data':json.loads(p.stdout)}


def runs(workflow):
    rows = {}; total = UNKNOWN; complete = False
    for page in range(1,21):
        r = api(f'actions/workflows/{workflow}/runs?per_page=100&page={page}')
        if r['access'] != 'PASS':
            return dict(access='BLOCKED', runs=list(rows.values()), total_count=total,
                        complete=False, reason=r['reason'])
        total = r['data']['total_count']
        batch = r['data']['workflow_runs']
        for x in batch:
            rows[x['id']] = {k:x.get(k) for k in ('id','status','conclusion','created_at',
                'updated_at','run_started_at','head_sha','event','head_branch')}
        if len(batch)<100 or len(rows)>=total:
            complete=True; break
    return dict(access='PASS', runs=sorted(rows.values(),key=lambda r:r['id'],reverse=True),
                total_count=total, complete=complete)


def diagnose(snapshot):
    """Same run ID cannot add throughput on a repeated observation; no additive ledger."""
    out = {}
    for name, listing in snapshot['workflows'].items():
        rows = {r['id']:r for r in listing.get('runs',[])}
        out[name] = {'unique_runs_in_query':len(rows), 'query_complete':listing.get('complete',False),
                     'last_run':max(rows.values(),key=lambda r:r['id']) if rows else UNKNOWN,
                     'execution': 'NO_EXECUTION' if not rows and listing.get('complete') and
                     listing['access']=='PASS' else 'UNKNOWN' if not rows else 'EXECUTED'}
    out['artifact_delivery'] = snapshot.get('artifact_access',UNKNOWN)
    # Pending is not EXCLUDED or a semantic outcome.
    out['semantic'] = snapshot.get('state_metrics', {k:UNKNOWN for k in
        ('completed_documents','pending_documents','oldest_pending_hours','REVIEW_LEAD',
         'HOLD','EXCLUDED','CONFIRMATION')})
    out['zero_interpretation'] = {
        'shadow_no_execution':out.get('SHADOW',{}).get('execution'),
        'artifact_delivery':snapshot.get('artifact_access',UNKNOWN),
        'no_new_capture':UNKNOWN, 'capture_failure':UNKNOWN,
        'semantic_reading_outcome':'NOT_INFERRED_FROM_PENDING_OR_ABSENT_STATE'}
    return out


def scheduled_slot(observed):
    dt=datetime.fromisoformat(observed)
    if dt.utcoffset() is None:
        raise ValueError('observed timestamp must include timezone')
    dt=dt.astimezone(timezone.utc)
    path=Path('.github/workflows/rss-live-check.yml');raw=path.read_bytes()
    crons=re.findall(r"cron:\s*['\"]([^'\"]+)['\"]",raw.decode())
    times=[]
    for cron in crons:
        match=re.fullmatch(r'(\d+) (\d+) \* \* \*',cron)
        if not match:return {'nominal_UTC':UNKNOWN,'reason':'UNSUPPORTED_CRON','source_sha256':sha(raw)}
        minute,hour=map(int,match.groups());times.append((hour,minute))
    if not times:return {'nominal_UTC':UNKNOWN,'reason':'NO_CRON','source_sha256':sha(raw)}
    options=[dt.replace(hour=h,minute=m,second=0,microsecond=0)+timedelta(days=d)
             for d in (-1,0,1) for h,m in times]
    return {'last_RSS_nominal_UTC':max(x for x in options if x<=dt).isoformat(),
            'next_RSS_nominal_UTC':min(x for x in options if x>dt).isoformat(),
            'source_sha256':sha(raw),'basis':'checked-out RSS workflow bytes',
            'acquisition_expected':'After successful RSS completion; no own cron',
            'shadow_expected':'After acquisition completion; conditional; no own cron',
            'late_tolerance':'UNAPPROVED', 'zero_alert_threshold':'UNAPPROVED'}


def read_state():
    p=subprocess.run(['git','ls-remote','origin','refs/heads/review-lead-shadow-state'],capture_output=True)
    if p.returncode:return {'access':'BLOCKED','metrics':UNKNOWN}
    if not p.stdout.strip():return {'access':'ABSENT','branch_exists':False,'activation':UNKNOWN,
        'metrics':{k:metric(0,'remote branch absent','current persisted SHADOW state',
                           'cards' if k in ('REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION') else 'documents')
                   for k in ('completed_documents','pending_documents','REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION')},
        'note':'No persisted SHADOW records; does not measure human research or undelivered capture queue.'}
    commit=p.stdout.decode().split()[0]
    p=subprocess.run(['git','fetch','--no-tags','origin','review-lead-shadow-state'],capture_output=True)
    if p.returncode:return {'access':'BLOCKED','commit':commit,'metrics':UNKNOWN}
    listing=subprocess.check_output(['git','ls-tree','-r',commit],text=True).splitlines()
    files={}; hashes={}
    for line in listing:
        head,path=line.split('\t',1)
        if head.split()[:2]!=['100644','blob'] or not path.startswith('review-lead-shadow/') or '..' in path.split('/'):
            return {'access':'BLOCKED','reason':'UNEXPECTED_STATE_TREE','metrics':UNKNOWN}
        raw=subprocess.check_output(['git','show',commit+':'+path]);hashes[path]=sha(raw)
        if path.endswith('.json'):
            value=json.loads(raw)
            if 'record_sha256' in value:
                from bct.review_leads import digest, VERSION
                from bct.objective_lock import require_objective
                require_objective(value)
                if value['record_sha256']!=digest({k:v for k,v in value.items() if k!='record_sha256'}) or value.get('review_rules_version')!=VERSION:
                    return {'access':'BLOCKED','reason':'STATE_INTEGRITY_MISMATCH','metrics':UNKNOWN}
            files[path]=value
    queue={(v['document_id'],v['body_sha256']):v for p,v in files.items() if '/queue/' in p}
    semantic={(v['document_id'],v['body_sha256']) for p,v in files.items() if '/semantic/' in p}
    pending=[v for k,v in queue.items() if k not in semantic]
    first=[v for p,v in files.items() if '/store/first/' in p]
    receipts=[v for p,v in files.items() if '/store/intake/' in p]
    ages=[]
    for v in pending:
        try:ages.append((datetime.now(timezone.utc)-datetime.fromisoformat(v['intake_recorded_at'])).total_seconds()/3600)
        except (KeyError,ValueError,TypeError):pass
    vals={'completed_documents':len(semantic),'pending_documents':len(pending),
          'oldest_pending_hours':max(ages) if ages and len(ages)==len(pending) else UNKNOWN,
          'deterministic_documents':len({(r['document_id'],r['body_sha256']) for r in receipts})}
    vals.update({s:sum(f['status']==s for f in first) for s in ('REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION')})
    return {'access':'PASS','commit':commit,'hashes':hashes,
        'activation':files.get('review-lead-shadow/shadow-activation.json',UNKNOWN),
        'metrics':{k:metric(v,commit,'current cumulative persisted state',
            'hours' if k=='oldest_pending_hours' else 'cards' if k in ('REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION') else 'documents') for k,v in vals.items()},
        'history_files':sum('/store/history/' in p for p in files)}


def collect(observer_id, prior=None):
    start=now();snapshot={'observed_at':start,'observer_run_id':observer_id,
        'last_observer_execution_at':prior.get('observed_at',UNKNOWN) if prior else UNKNOWN,
        'workflows':{}, 'scheduled':scheduled_slot(start)}
    for name,wf in [('RSS','rss-live-check.yml'),('acquisition','precursor-acquisition.yml'),('SHADOW','review-lead-shadow.yml')]:
        snapshot['workflows'][name]=runs(wf)
        snapshot['workflows'][name]['definition']=api('actions/workflows/'+wf)
        rr=snapshot['workflows'][name]['runs']
        if rr:
            snapshot['workflows'][name]['last_jobs']=api(f"actions/runs/{rr[0]['id']}/jobs?per_page=100")
    snapshot['flag']=api('actions/variables/BCT_REVIEW_SHADOW_ENABLED')
    a=snapshot['workflows']['acquisition']['runs']
    if a:
        listing=api(f"actions/runs/{a[0]['id']}/artifacts?per_page=100")
        snapshot['artifacts']=listing
        if listing['access']=='PASS':
            listing['data']={'total_count':listing['data']['total_count'],'artifacts':[
                {k:v.get(k) for k in ('id','name','created_at','expires_at','expired','size_in_bytes')}
                for v in listing['data']['artifacts']]}
            artifact=next((x for x in listing['data']['artifacts'] if x['name']=='precursor-private-cache'),None)
            if artifact:
                # Read response only, never extract or execute artifact content.
                p=subprocess.run(['gh','api',f"repos/{REPO}/actions/artifacts/{artifact['id']}/zip"],capture_output=True)
                snapshot['artifact_access']={'artifact_id':artifact['id'],
                    'download':'PASS' if p.returncode==0 else 'BLOCKED',
                    'restore':'NOT_PERFORMED', 'reason':None if p.returncode==0 else 'ARTIFACT_DOWNLOAD_DENIED',
                    'response_sha256':sha(p.stdout) if p.returncode==0 else UNKNOWN}
            else:snapshot['artifact_access']={'download':'MISSING','restore':'NOT_PERFORMED'}
    state=read_state();snapshot['state']=state;snapshot['state_metrics']=state.get('metrics',UNKNOWN)
    snapshot['run_delta_metrics']=metric(UNKNOWN,'No prior observer checkpoint / unavailable run audit','latest run increase')
    snapshot['data_index']={'access':'UNKNOWN'}
    p=subprocess.run(['git','fetch','--no-tags','origin','data'],capture_output=True)
    if not p.returncode:
        commit=subprocess.check_output(['git','rev-parse','FETCH_HEAD'],text=True).strip()
        p=subprocess.run(['git','show',commit+':precursor-index.json'],capture_output=True)
        if not p.returncode:snapshot['data_index']={'access':'PASS','commit':commit,'sha256':sha(p.stdout),'value':json.loads(p.stdout)}
    snapshot['diagnosis']=diagnose(snapshot);snapshot['observer_completed_at']=now()
    index=snapshot['data_index']
    snapshot['throughput']={
        'new_verified_documents':metric(index['value']['new_verified_documents'],
            'data:precursor-index.json at '+index['commit'],
            'acquisition run '+str(index['value']['cache_run_id'])) if index.get('access')=='PASS'
            else metric(UNKNOWN,'data index inaccessible','latest acquisition'),
        'captures':metric(UNKNOWN,'private cache not restored','latest acquisition'),
        'new_pending':metric(UNKNOWN,'no per-run audit available','latest SHADOW run'),
        'unique_origins':metric(UNKNOWN,'source bodies unavailable','latest run','origins'),
        'unique_targets':metric(UNKNOWN,'source bodies unavailable','latest run','targets')}
    snapshot['code_basis']={str(p):sha(p.read_bytes()) for p in
        [Path('src/bct/review_intake.py'),Path('src/bct/review_shadow.py'),
         Path('src/bct/review_leads.py'),Path('review-leads/contract.json'),
         Path('BCT_OBJECTIVE_LOCK.md')]}
    snapshot['main_ref']=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],text=True).strip()
    snapshot['limitations']=['Metadata query completion recorded per workflow; job details only latest run.',
        'Artifact restoration and body verification not implied by artifact metadata.',
        'No semantic AI or manual service in production workflow; --semantic attributed packets required.',
        'GitHub-hosted observer shares GitHub failure domain; not independent external monitoring.',
        'No automatic alarms: tolerance and budget unapproved. No t0, cohort or formal evaluation activation.']
    return snapshot


def validate_state_ref(ref):
    if ref!=STATE_REF:raise ValueError('EVALUATION_STATE_REF_ONLY')
    return ref


def draft_epoch(config):
    if config['status']!='DRAFT' or config.get('t0') is not None or config.get('epoch') is not None:
        raise ValueError('UNAPPROVED_ACTIVATION')
    return None


def hypothesis_sidecar(bundle, card, value):
    from bct import review_leads as r
    for k in ('target','scope_fields','observed_changes','claim','assumptions',
              'prediction_period','refutation_conditions','evidence','exposure'):
        if k not in value:raise ValueError('SIDECAR_FIELD_REQUIRED:'+k)
    docs=r.documents(bundle)
    for ref in value['evidence']:r.reference(ref,docs)
    for fact in value['observed_changes']:r.reference(fact['reference'],docs)
    r.validate_fields(value['scope_fields'],docs)
    exposure=value['exposure']
    for k in ('input_documents','started_at','completed_at','annotator','method','web_search_used',
              'search_references','model_knowledge_basis'):assert k in exposure,k
    for d in exposure['input_documents']:
        assert docs[d['document_id']]['body_sha256']==d['body_sha256']
    assert value['hypothesis_version'] in ('H0','H1')
    if value['hypothesis_version']=='H1':
        assert value.get('previous_hypothesis_hash') and value.get('previous_recorded_at')
    assert value['recorded_at']!=UNKNOWN
    for t in [value['recorded_at'],exposure['started_at'],exposure['completed_at']]:
        if t!=UNKNOWN:assert datetime.fromisoformat(t).tzinfo is not None
    if value['hypothesis_version']=='H1':
        assert datetime.fromisoformat(value['recorded_at'])>datetime.fromisoformat(value['previous_recorded_at'])
    # Sidecar anchors the card's exact immutable time; no caller-provided backdating.
    claims={k:value[k] for k in ('scope_fields','claim','assumptions','prediction_period','refutation_conditions')}
    return {**value,'schema_version':'BCT_A_HYPOTHESIS_SIDECAR_1',
        'sidecar_recorded_at':now(),'review_id':card['review_id'],
        'first_card_sha256':card.get('record_sha256',r.digest(card)),
        'card_hash_basis':'existing hash-field-excluded record_sha256, or canonical supplied card when unsealed',
        'review_lead_first_at':card['first_review_recorded_at'] if card['status']=='REVIEW_LEAD' else UNKNOWN,
        'market_candidate_first_at':UNKNOWN,'T_scope':UNKNOWN,'hypothesis_hash':r.digest(claims),
        'historical_annotation_completion':UNKNOWN,'cohort':'EXPLORATORY_EXCLUDED','performance_evaluation':False}


def validate_draft(directory):
    directory=Path(directory);config=json.loads((directory/'config.json').read_text())
    draft_epoch(config);validate_state_ref(config['state_ref'])
    text=(directory/config['authoritative_document']).read_text()
    assert config['version'] in text and 't0=null' in text and 'epoch=null' in text
    assert config['checkpoint_proposal_days']==[7,14] and config['checkpoint_approved'] is False
    assert config['interest_horizon_months']==[12,36] and '12–36' in text
    assert config['formal_protocol_approved'] is False
    for k in ('review_minutes_budget','cost_budget','lateness_tolerance_minutes','zero_alert_threshold'):
        assert config[k] is None
    return sha((directory/config['authoritative_document']).read_bytes())


def validate_approved(directory):
    directory=Path(directory)
    config=json.loads((directory/'approved-config.json').read_text())
    manifest=json.loads((directory/'approved-manifest.json').read_text())
    raw=(directory/'PREREGISTRATION_APPROVED.md').read_bytes()
    if config['status']!='APPROVED_A_ONLY' or manifest['preregistration_sha256']!=sha(raw):
        raise ValueError('APPROVED_DOCUMENT_BINDING_FAILED')
    for filename,key in [('approved-config.json','config_sha256'),
                         ('APPROVAL_RECORD.md','approval_evidence_sha256'),
                         ('PREREGISTRATION_DRAFT.md','original_draft_sha256')]:
        if sha((directory/filename).read_bytes())!=manifest[key]:raise ValueError('APPROVAL_HASH_MISMATCH')
    if config['checkpoint_days']!=[7,14] or config['formal_protocol_approved']:
        raise ValueError('APPROVAL_SCOPE_MISMATCH')
    validate_state_ref(config['state_ref'])
    return manifest


def validate_epoch(value,directory='review-leads/evaluation-a'):
    approved=validate_approved(directory)
    if value['preregistration_sha256']!=approved['preregistration_sha256'] or value['version']!=approved['version']:
        raise ValueError('EPOCH_DOCUMENT_MISMATCH')
    event=value['server_event']
    if event['head_branch']!='main' or event['head_sha']!=value['main_sha'] or event['created_at']!=value['t0'] or event['event']!='push':
        raise ValueError('SERVER_EVENT_BINDING_FAILED')
    t0=datetime.fromisoformat(value['t0'].replace('Z','+00:00'))
    if t0.tzinfo is None or not event['id']:raise ValueError('SERVER_TIME_REQUIRED')
    if value['formal_evaluation_started'] or value['B_stage_started']:raise ValueError('B_NOT_APPROVED')
    return value


def guard_output(parent):
    parent=Path(parent)
    if parent.name!='evaluation-a' or parent.is_symlink():raise ValueError('A_OUTPUT_NAMESPACE_ONLY')
    for ancestor in [parent,*parent.parents]:
        if ancestor.name in ('live-state','review-lead-shadow','review-lead-shadow-state','data'):
            raise ValueError('OPERATIONAL_STORE_FORBIDDEN')
        if any((ancestor/name).exists() for name in ('session.json','shadow-activation.json','activation.json')):
            raise ValueError('OPERATIONAL_STORE_FORBIDDEN')
        if ancestor.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
    return parent


def append_sidecar(parent,record):
    parent=guard_output(parent)
    target=parent/'sidecars'
    if target.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
    target.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2).encode()
    path=target/(sha(raw)+'.json')
    if path.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
    if path.exists():
        assert path.read_bytes()==raw
    else:
        with path.open('xb') as stream:stream.write(raw)
    return path


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--observer-id',default=None);p.add_argument('--prior-report',type=Path)
    p.add_argument('--epoch',type=Path)
    a=p.parse_args()
    if a.output.parent.name=='reports':
        guard_output(a.output.parent.parent)
        if a.output.parent.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
    else:guard_output(a.output.parent)
    if a.output.exists():raise ValueError('IMMUTABLE_REPORT_ALREADY_EXISTS')
    prior=json.loads(a.prior_report.read_text()) if a.prior_report else None
    report=collect(a.observer_id or 'local-'+uuid.uuid4().hex,prior)
    if a.epoch:
        epoch=validate_epoch(json.loads(a.epoch.read_text()))
        report['evaluation_link']={'phase':'SHAKEDOWN_OBSERVATION','epoch':epoch['epoch'],
            't0':epoch['t0'],'preregistration_sha256':epoch['preregistration_sha256'],
            'note':'Observer linkage only; no card mode/cohort/activation is rewritten.'}
    report['runtime']='github_actions' if __import__('os').environ.get('GITHUB_ACTIONS')=='true' else 'cloud_tool'
    rss=report['diagnosis']['RSS']['last_run']
    report['actual_RSS_schedule_delay_seconds']=UNKNOWN
    if isinstance(rss,dict) and rss.get('event')=='schedule':
        slot=scheduled_slot(rss['created_at']).get('last_RSS_nominal_UTC')
        if slot:
            report['actual_RSS_schedule_delay_seconds']=(datetime.fromisoformat(rss['created_at'].replace('Z','+00:00'))-datetime.fromisoformat(slot)).total_seconds()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)


if __name__=='__main__':main()
