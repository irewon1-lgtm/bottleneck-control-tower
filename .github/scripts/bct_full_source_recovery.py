"""Gate 3: account for every failed version; never fabricate old full text."""
import json
import os
from pathlib import Path
import threading
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlsplit

from bct.future_body import access_failure, extract_document, cache_body
from bct.future_bottleneck import fetch_html
from bct.future_github import GitHubTransport
from bct.future_review import failure_index


def main():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    report=json.loads((root/'checkpoint.json').read_text())
    if any(report.get('gate'+str(i))!='PASS' for i in range(3)):
        raise RuntimeError('previous gates did not pass')
    transport=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
    tracking=transport.read('future-tracking.json')
    failed=list(failure_index(tracking.document).values())
    urls={r['url'] for r in failed}
    groups=defaultdict(deque)
    for url in sorted(urls):groups[urlsplit(url).hostname].append(url)
    order=[]
    while any(groups.values()):
        for host in groups:
            if groups[host]:order.append(groups[host].popleft())
    cache=root/'private-source-cache';cache.mkdir(exist_ok=True)
    locks={host:threading.Lock() for host in groups}
    last_access={host:0.0 for host in groups}
    cooldown={}
    deadline=time.monotonic()+25*60
    def inspect(url):
        host=urlsplit(url).hostname
        result={'url':url,'attempted_at':datetime.now(timezone.utc).isoformat(),
                'environment':'GITHUB_HOSTED_RUNNER','http_request_completed':False}
        with locks[host]:
            if time.monotonic()>=deadline:
                return {**result,'status':'SOURCE_WAIT','reason':'RUNNER_DEADLINE','attempted':False}
            if host in cooldown:
                return {**result,'status':'SOURCE_WAIT','reason':'HOST_RATE_LIMIT',
                        'resume_after':cooldown[host],'attempted':False}
            delay=1.0-(time.monotonic()-last_access[host])
            if delay>0:time.sleep(delay)
            last_access[host]=time.monotonic()
            result['attempted']=True
            try:
                fetched=fetch_html(url)
                result.update(http_request_completed=True,http_status=fetched['status'])
                body=extract_document(fetched['html'],http_status=fetched['status'],content_type=fetched['content_type'])
                if fetched.get('truncated'):
                    if body['body_status']=='FULL':body['body_status']='PARTIAL'
                    body.setdefault('reasons',[]).append('BODY_DOWNLOAD_TRUNCATED')
                result.update({k:body.get(k) for k in ('body_status','body_sha256','body_chars','reasons','completeness','extraction_method')})
                if body.get('body'):
                    digest=cache_body(cache,body['body'])
                    if digest!=body['body_sha256']:raise RuntimeError('private cache hash mismatch')
                reasons=set(body.get('reasons',[]))
                result['status']='BLOCKED' if reasons & {'ACCESS_CHALLENGE','PAYWALL_OR_LOGIN_PREVIEW'} else body['body_status']
                result['access_diagnostic']={'category':'HTTP_OK','state':result['status'],'retryable':False}
            except Exception as exc:
                diagnostic=access_failure(exc)
                result.update(status=diagnostic['state'],body_status='UNAVAILABLE',access_diagnostic=diagnostic)
                if diagnostic['category'].startswith('HTTP_'):
                    result.update(http_request_completed=True,http_status=diagnostic['http_status'])
                if diagnostic['category']=='HTTP_429':
                    cooldown[host]=time.time()+(diagnostic.get('retry_after_seconds') or 3600)
            return result
    observations={}
    journal=root/'source-recovery-attempts.jsonl'
    with journal.open('w') as stream,ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(inspect,url):url for url in order}
        for future in as_completed(futures):
            result=future.result();observations[result['url']]=result
            stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
    versions=[]
    for prior in failed:
        result=observations[prior['url']]
        expected=prior.get('body_sha256')
        exact=result.get('body_status')=='FULL' and bool(expected) and result.get('body_sha256')==expected
        versions.append({'document_id':prior['document_id'],'source_version':prior.get('source_version'),
            'old_body_sha256':expected,'old_failure':prior['reason'],'url':prior['url'],
            'observed_body_sha256':result.get('body_sha256'),'status':result['status'],
            'exact_version_recovered':exact,'new_snapshot_observed':bool(result.get('body_sha256')) and result.get('body_sha256')!=expected,
            'attempted':result['attempted'],'prior_history_retained':True})
    if len(versions)<3696 or len(observations)!=len(urls):raise RuntimeError('failed version inventory lost')
    source_errors=[x for x in observations.values() if x['status']=='ERROR']
    not_attempted=[x for x in observations.values() if not x['attempted']]
    (root/'source-recovery-versions.json').write_text(json.dumps(versions,ensure_ascii=False,indent=2)+'\n')
    recovered={reason:sum(v['old_failure']==reason and v['exact_version_recovered'] for v in versions)
               for reason in {v['old_failure'] for v in versions}}
    report.update(stage=3,recovery_urls=len(urls),recovery_versions=len(versions),
        recovery_url_statuses=dict(Counter(x['status'] for x in observations.values())),
        recovery_exact_versions=recovered,recovery_system_errors=len(source_errors),
        recovery_urls_not_attempted=len(not_attempted),production_source_records_changed=False,
        reader_completions_added=0,original_184_completions_preserved=True)
    if source_errors:
        report.update(status='FAIL',gate3='FAIL',error='SOURCE_RECOVERY_TECHNICAL_ERRORS',
                      resume_condition='Fix recorded source errors and restart from Stage 0')
    elif not_attempted:
        report.update(status='BLOCKED',gate3='BLOCKED',error='SOURCE_RECOVERY_DEFERRED',
                      resume_condition='Resume unattempted URLs from preserved journal after cooldown/new runner; restart at Stage 0')
    else:
        report.update(status='PASS',gate3='PASS',next_stage=4,
                      resume_condition='Evidence supplement and queue recovery must pass before publication/automatic reading')
    report['source_recovery_finished_at']=datetime.now(timezone.utc).isoformat()
    (root/'checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','stage','recovery_urls','recovery_versions','recovery_system_errors','recovery_urls_not_attempted','recovery_exact_versions')}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
