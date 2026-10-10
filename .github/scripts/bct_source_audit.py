"""Gate 2: original URLs on a real runner, preserving exact-version history."""
import json
import os
from pathlib import Path
import socket
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from datetime import datetime, timezone
from typing import Any

from bct.future_body import access_failure, extract_document, cache_body
from bct.future_bottleneck import fetch_html, screen
from bct.future_github import GitHubTransport
from bct.future_review import failure_index


def main():
    root = Path(os.environ['RUNNER_TEMP']) / 'bct-recovery'
    report = json.loads((root / 'checkpoint.json').read_text())
    if report.get('gate0') != 'PASS' or report.get('gate1') != 'PASS':
        raise RuntimeError('previous gates did not pass')
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    original = transport.read('future-candidates.json')
    report['source_audit_candidate_blob'] = original.sha
    tracking = transport.read('future-tracking.json')
    failures = failure_index(tracking.document)
    selected: dict[str | None,dict[str,Any]] = {}
    # Cover every failed DNS host and official sources; a sample is never
    # presented as recovery of all 1,693 original document versions.
    for item in failures.values():
        url = item.get('url')
        if not url:
            continue
        host = urlsplit(url).hostname
        if item['reason'] == 'ENVIRONMENT_DNS_RESOLUTION_FAILED':
            selected.setdefault(host, item)
    official = [x for x in failures.values() if urlsplit(x.get('url') or '').hostname in
                ('www.nist.gov', 'www.eia.gov', 'www.esa.int', 'www.fda.gov')]
    for i, item in enumerate(official[:8]):
        selected['official-' + str(i)] = item
    selected = {item['url']:item for item in selected.values()}
    cache = root / 'private-source-cache';cache.mkdir(exist_ok=True)
    def inspect(item):
        url = item['url'];host = urlsplit(url).hostname
        result = {'document_id':item['document_id'], 'source_version':item.get('source_version'),
                  'old_body_sha256':item.get('body_sha256'), 'old_failure':item['reason'],
                  'url':url, 'host':host, 'execution_environment':'GITHUB_HOSTED_RUNNER',
                  'attempted_at':datetime.now(timezone.utc).isoformat(), 'http_request_completed':False}
        try:
            socket.getaddrinfo(host, 443)
            result['dns_resolved'] = True
            fetched = fetch_html(url)
            result.update(http_request_completed=True, http_status=fetched['status'])
            body = extract_document(fetched['html'], http_status=fetched['status'], content_type=fetched['content_type'])
            if fetched.get('truncated'):
                if body['body_status']=='FULL':body['body_status']='PARTIAL'
                body.setdefault('reasons',[]).append('BODY_DOWNLOAD_TRUNCATED')
            result.update({k:body.get(k) for k in ('body_status','body_sha256','body_chars','reasons','completeness','extraction_method')})
            if body.get('body'):
                cache_body(cache, body['body'])
                result['screening'] = screen(body['body'])
            reasons = set(body.get('reasons', []))
            result['access_diagnostic'] = {'category':'PAYWALL' if 'PAYWALL_OR_LOGIN_PREVIEW' in reasons else
                'ACCESS_CHALLENGE' if 'ACCESS_CHALLENGE' in reasons else 'HTTP_OK',
                'state':'SOURCE_BLOCKED' if reasons & {'PAYWALL_OR_LOGIN_PREVIEW','ACCESS_CHALLENGE'} else
                'AVAILABLE' if body['body_status']=='FULL' else 'SOURCE_WAIT', 'retryable':False}
            result['exact_failed_body_recovered'] = (body['body_status']=='FULL' and
                body.get('body_sha256') == item.get('body_sha256'))
        except Exception as exc:
            diagnostic = access_failure(exc)
            result.update(body_status='UNAVAILABLE', access_diagnostic=diagnostic,
                          exact_failed_body_recovered=False)
            if diagnostic['category'].startswith('HTTP_'):
                result.update(http_request_completed=True,http_status=diagnostic['http_status'])
            if diagnostic['category']=='DNS_RESOLUTION_FAILED':
                result['dns_resolved'] = False
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(inspect, selected.values()))
    (root / 'source-audit.json').write_text(json.dumps(outcomes, ensure_ascii=False, indent=2)+'\n')
    errors = [x for x in outcomes if x['access_diagnostic']['state']=='ERROR']
    dns_remaining = [x for x in outcomes if x.get('dns_resolved') is False]
    http_ok = [x for x in outcomes if x.get('http_status')==200]
    report.update(stage=2, sample_sources=len(outcomes), sample_http_completed=sum(x['http_request_completed'] for x in outcomes),
                  sample_http_200=len(http_ok), sample_full=sum(x.get('body_status')=='FULL' for x in outcomes),
                  sample_dns_failures=len(dns_remaining), sample_system_errors=len(errors),
                  sample_exact_failed_versions_recovered=sum(x['exact_failed_body_recovered'] for x in outcomes),
                  sample_categories=dict(Counter(x['access_diagnostic']['category'] for x in outcomes)),
                  source_records_changed=False, originals_and_history_preserved=True)
    if errors:
        report.update(status='FAIL', gate2='FAIL', error='SOURCE_ADAPTER_ERRORS',
                      resume_condition='Fix the recorded collector errors; restart at Stage 0')
    elif not http_ok or dns_remaining:
        report.update(status='BLOCKED', gate2='BLOCKED', error='SOURCE_ACCESS_ENVIRONMENT_INCOMPLETE',
                      resume_condition='Resolve recorded DNS/access environment failures; restart at Stage 0')
    else:
        report.update(status='PASS', gate2='PASS', next_stage=3,
                      resume_condition='Full recovery inventory and version matching required before Gate 3')
    (root / 'checkpoint.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','stage','sample_sources','sample_http_200','sample_full','sample_dns_failures','sample_system_errors')}))
    return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
