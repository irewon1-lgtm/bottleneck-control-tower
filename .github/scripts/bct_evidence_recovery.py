"""Gate 4: actual original captures, missing-field audit, bounded official search.

Assessments never become reader completions, candidate scores or human labels.
An unknown TARGET produces an explicit scope hold, never a general query.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit, urlencode
import xml.etree.ElementTree as ET

from bct.future_bottleneck import fetch_capture
from bct.recovery_capture import capture, cached_body
from bct.recovery_evidence import assess, source_document
from bct.precursor_source_search import bounded_plan, select_urls, validate_capture


def main():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    checkpoint=root/'checkpoint.json';report=json.loads(checkpoint.read_text())
    if any(report.get('gate'+str(i))!='PASS' for i in range(4)):
        raise RuntimeError('previous evidence-recovery gates did not pass')
    versions=[v for v in json.loads((root/'source-recovery-versions.json').read_text())
              if v['old_failure']=='REQUIRED_EVIDENCE_MISSING']
    baseline=json.loads(Path('config/bct-recovery-preservation.json').read_text())
    if len(versions)!=74 or len({(v['document_id'],v['source_version'],v['old_body_sha256']) for v in versions})!=74:
        raise RuntimeError('evidence failure inventory differs from preserved 74 versions')
    # Frozen baseline is verified by Gate 0; retain its identity in each receipt.
    baseline_hash=hashlib.sha256(json.dumps(baseline,sort_keys=True).encode()).hexdigest()
    hosts={urlsplit(v['url']).hostname for v in versions}
    locks={h:threading.Lock() for h in hosts};last={h:0.0 for h in hosts};blocked={}
    observations={};rows=[];requests={};searches=[];errors=[]
    def acquire(url):
        host=urlsplit(url).hostname
        with locks[host]:
            if host in blocked:
                return {'url':url,'attempted':False,'body_status':'UNAVAILABLE',
                        'status':'SOURCE_WAIT','reason':'HOST_RATE_LIMIT',**blocked[host]}
            delay=1.0-(time.monotonic()-last[host])
            if delay>0:time.sleep(delay)
            last[host]=time.monotonic()
            observation=capture(url,root)
            diagnostic=observation.get('access_diagnostic',{})
            if diagnostic.get('category')=='HTTP_429':
                blocked[host]={'resume_after':time.time()+(diagnostic.get('retry_after_seconds') or 3600)}
            return observation
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for observation in pool.map(acquire,sorted({v['url'] for v in versions})):
                observations[observation['url']]=observation
        for version in versions:
            observation=observations[version['url']];body=cached_body(root,observation)
            document=source_document(version['document_id'],observation,body) if body else None
            assessment=assess(document)
            plan=bounded_plan(assessment['search_plan'])
            for request in plan['requests']:
                if request.get('search_scope_ready'):
                    requests.setdefault(request['request_id'],{'request':request,'document':document})
            rows.append({**version,'observed_body_sha256':observation.get('body_sha256'),
                         'original_failure_retained':True,'assessment':assessment,
                         'search_plan':plan,'preservation_baseline_sha256':baseline_hash})
        # Public original URLs and explicit user-authorized scoped searches.
        # Results are leads until actual primary-body and exact-scope checks.
        search_raw=root/'private-evidence-search';search_raw.mkdir(exist_ok=True)
        for value in requests.values():
            request=value['request'];seed=value['document'];attempt={
                'request_id':request['request_id'],'query':request['query'],
                'external_query_authorized':True,'attempted_at':datetime.now(timezone.utc).isoformat()}
            try:
                url='https://www.bing.com/search?'+urlencode({'q':request['query'],'format':'rss'})
                response=fetch_capture(url)
                if response['truncated']:raise ValueError('truncated search capture')
                raw=response['raw'];digest=hashlib.sha256(raw).hexdigest()
                (search_raw/(digest+'.xml')).write_bytes(raw)
                items=ET.fromstring(raw)
                urls=select_urls([i.findtext('link') for i in items.findall('.//item') if i.findtext('link')])
                results=[]
                for candidate_url in urls:
                    observation=capture(candidate_url,root);body=cached_body(root,observation)
                    document=source_document('supplement-'+hashlib.sha256(candidate_url.encode()).hexdigest(),observation,body) if body else None
                    results.append({'observation':observation,'validation':validate_capture(request,document,[seed]) if document else {'state':'SOURCE_UNAVAILABLE','new_evidence':0}})
                attempt.update(status='SEARCH_COMPLETED',raw_sha256=digest,results=results)
            except Exception as exc:
                from bct.future_body import access_failure
                diagnostic=access_failure(exc);attempt.update(status=diagnostic['state'],access_diagnostic=diagnostic)
                if diagnostic['state']=='ERROR':errors.append(diagnostic)
                searches.append(attempt)
                # A provider access failure is a recorded resume condition;
                # stop requests rather than repeat the same restriction.
                break
            searches.append(attempt)
        errors.extend(x for x in observations.values() if x['status']=='ERROR')
        deferred=[x for x in observations.values() if not x['attempted']]
        unfinished=len(requests)-sum(x.get('status')=='SEARCH_COMPLETED' for x in searches)
        result='FAIL' if errors else 'BLOCKED' if deferred or unfinished else 'PASS'
        report.update(stage=4,status=result,gate4=result,evidence_versions_audited=len(rows),
            full_clean_status='BLOCKED',full_clean_count=0,
            full_clean_reason='OPERATIONAL_READER_AND_STAGES_5_TO_FULL_NOT_CONNECTED',
            evidence_version_states=dict(Counter(x['assessment']['state'] for x in rows)),
            evidence_missing_fields=dict(Counter(f for x in rows for f in x['assessment']['missing_fields'])),
            evidence_original_http_requests=sum(x['attempted'] for x in observations.values()),
            evidence_scoped_requests=len(requests),evidence_searches_completed=len(requests)-unfinished,
            evidence_scope_held_versions=sum(not any(r.get('search_scope_ready') for r in x['search_plan']['requests']) for x in rows),
            evidence_system_errors=len(errors),reader_completions_added=0,
            evidence_supplement_promotions=0,prediction_performance='UNVERIFIED',
            next_stage=5 if result=='PASS' else 4,
            resume_condition='Actual semantic reading and 7-state queue recovery required; all evidence holds preserved' if result=='PASS' else 'Resolve recorded evidence access/technical restriction; restart Stage 0')
    except Exception as exc:
        report.update(stage=4,status='FAIL',gate4='FAIL',error_type=type(exc).__name__,
                      error=str(exc),resume_condition='Fix evidence executor; restart Stage 0')
        raise
    finally:
        (root/'evidence-recovery-observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2)+'\n')
        (root/'evidence-recovery-versions.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        (root/'evidence-recovery-searches.json').write_text(json.dumps(searches,ensure_ascii=False,indent=2)+'\n')
        report['evidence_recovery_finished_at']=datetime.now(timezone.utc).isoformat()
        checkpoint.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('stage','status','gate4','evidence_versions_audited','evidence_scoped_requests','evidence_searches_completed','evidence_system_errors')}))
    return 0 if report['gate4']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
