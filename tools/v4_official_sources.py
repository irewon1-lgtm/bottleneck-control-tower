#!/usr/bin/env python3
"""Manual, bounded, resumable official-format collection into the Q1/Q2 Ledger.

No schedule, AI, model loading, private writer token, or candidate registration.
Uses the existing public transport, Ledger and private monthly publisher.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bct.objective_lock import require_objective, stamp_export
from bct.target_acquisition import fetch
from bct.v4 import official_sources as fmt
from bct.v4.official_credentials import bindings
from bct.v4.store import Ledger, file_sha, now, sha

REG = Path('docs/v4/quantitative/source-registry.json')
ROOT = Path('var/v4/quantitative/global-sources')
PREFIX = 'OFFICIAL_SOURCE_PAGE:'


def redirect_identity(source, original, final):
    """NESO's published resource redirects to its own signed download CDN.

    Accept only this verified resource-ID/path mapping, no broad R2 allowlist,
    no Authorization header, and never retain the signed query values.
    """
    u = urlsplit(final)
    if source == 'neso' and u.hostname == '83025b28472d6aa2bf5ae59f3724aa78.eu.r2.cloudflarestorage.com':
        import re
        match = re.fullmatch(r'/dataset/[0-9a-f-]{36}/resource/([0-9a-f-]{36})/download/([^/]+\.csv)', urlsplit(original).path)
        allowed = {'response-content-disposition', 'response-content-type', 'X-Amz-Algorithm', 'X-Amz-Expires', 'X-Amz-Credential', 'X-Amz-SignedHeaders', 'X-Amz-Date', 'X-Amz-Signature'}
        if (not match or u.scheme != 'https' or u.username or u.password
                or u.path != '/dx-national-grid/national-grid/resources/'+match[1]+'/'+match[2]
                or set(dict(parse_qsl(u.query)))-allowed): raise ValueError('NESO_RESOURCE_REDIRECT_IDENTITY')
        return urlunsplit((u.scheme, u.netloc, u.path, '', '')), True
    fmt.safe_url(source, final)
    return final, False


def canonical(url):
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(sorted(parse_qsl(u.query))), ''))


class Capture:
    def __init__(self, root, *, network=False, max_calls=32, seconds=90):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.network = network; self.calls = 0; self.max_calls = max_calls
        self.started = time.monotonic(); self.seconds = seconds
        self.index = {}; self.held_hosts = set(); self.invalid_receipts = set()
        for p in self.root.glob('*.json'):
            try: m = json.loads(p.read_text())
            except (ValueError, UnicodeError): self.invalid_receipts.add(p.stem); continue
            if 'url' not in m: continue
            self.index[canonical(m['url'])+('|'+m['transport_contract'] if m.get('transport_contract') else '')] = p
            if m.get('status') in (401, 403, 429): self.held_hosts.add(urlsplit(m['url']).hostname)

    def get(self, source, url):
        fmt.safe_url(source, url); key = canonical(url)
        contract = 'Q1_EXISTING_20MB' if source == 'canadabuys' else None
        if contract: key += '|'+contract
        if sha(url.encode()) in self.invalid_receipts: return None, {'status': 'CORRUPT_CACHE_RECEIPT', 'url': url}
        if key in self.index:
            p = self.index[key]; m = json.loads(p.read_text())
            if m.get('status') != 200: return None, m
            raw = p.with_suffix('.raw')
            if not raw.exists() or file_sha(raw) != m['raw_sha256']: raise ValueError('SOURCE_CACHE_HASH_MISMATCH')
            final, redacted = redirect_identity(source, url, m.get('final_url', url))
            if redacted:
                m.update(final_url=final, signed_download_parameters_redacted=True)
                p.write_text(json.dumps(m))
            return raw.read_bytes(), m
        if not self.network: return None, {'status': 'NOT_FETCHED_OFFLINE', 'url': url}
        if self.calls >= self.max_calls or time.monotonic()-self.started >= self.seconds: return None, {'status': 'BATCH_LIMIT_PENDING', 'url': url}
        if urlsplit(url).hostname in self.held_hosts: return None, {'status': 'HOST_QUARANTINED', 'url': url}
        # Journal BEFORE the call: a killed call cannot be silently retried.
        p = self.root/((sha([url, contract]) if contract else sha(url.encode()))+'.json')
        m = {'url': url, 'purpose': 'DATA', 'status': 'INTERRUPTED_NO_AUTO_RETRY', 'acquired_at': now()}
        if contract: m['transport_contract'] = contract
        p.write_text(json.dumps(m)); self.index[key] = p; self.calls += 1
        try:
            if contract:
                # Existing Q1 SourceClient already caps files at20,000,000B.
                # The16,172,272B public Canada file was independently HEAD-sized.
                # This is not an increase of the authoritative registry cap.
                from bct.v4.adapters import SourceClient
                raw, final, status, content_type = SourceClient().fetch(url)
            else: raw, final, status, content_type = fetch(url)
            final, redacted = redirect_identity(source, url, final)
            if status != 200 or not raw: raise ValueError('NON200_OR_EMPTY')
            p.with_suffix('.raw').write_bytes(raw)
            m.update(status=status, final_url=final, signed_download_parameters_redacted=redacted, bytes=len(raw), raw_sha256=sha(raw), content_type=content_type)
        except Exception as exc:
            status = getattr(exc, 'code', None)
            safe_reason = str(exc) if isinstance(exc, ValueError) and str(exc) in {'SOURCE_CACHE_HASH_MISMATCH', 'OFFICIAL_SOURCE_URL_NOT_REVIEWED', 'NESO_RESOURCE_REDIRECT_IDENTITY', 'response exceeds bounded 4MB capture'} else type(exc).__name__
            m.update(status=status or 'TRANSPORT_OR_SIZE_FAILURE', error_type=safe_reason, retry=False)
            if status in (401, 403, 429): self.held_hosts.add(urlsplit(url).hostname)
            retry_after = getattr(exc, 'headers', {}).get('Retry-After') if getattr(exc, 'headers', None) else None
            if retry_after and retry_after.isdecimal(): m['retry_after_seconds'] = int(retry_after)
            raw = None
        p.write_text(json.dumps(m))
        return raw, m


def parse(raw, receipt, job):
    acquired = receipt.get('acquired_at') or datetime.fromtimestamp(receipt['at'], timezone.utc).isoformat()
    meta = {'source_id': job['source_id'], 'url': receipt['url'], 'sha256': sha(raw), 'acquired_at': acquired, 'published_at': job.get('published_at', 'UNKNOWN')}
    if receipt['raw_sha256'] != meta['sha256']: raise ValueError('SOURCE_HASH_MISMATCH')
    extra = {}
    if job['format'] == 'HTML_REVIEW':
        records, native = fmt.reviewed_html(raw, meta, job['source_review']); nxt = None
    elif job['format'] == 'CSV':
        records, native = fmt.parse_csv(raw, meta, scope=job.get('scope')); nxt = None
        extra['CSV_records_scanned'] = len(native)
        extra['CSV_records_selected'] = len(records)
        extra['fixed_publication_scope'] = job.get('scope')
    elif job['format'] == 'XLSX':
        from io import BytesIO
        from openpyxl import load_workbook
        native = load_workbook(BytesIO(raw), read_only=False, data_only=True)
        records, extra = fmt.parse_ercot(native, meta); nxt = None
    else:
        native = json.loads(raw); records, nxt = fmt.parse_json(native, meta)
        if job.get('source_review_annotations'):
            extra['held_source_reviews'] = []
            for annotation in job['source_review_annotations']:
                try: records += fmt.reviewed_item_descriptions(native, meta, [annotation])
                except ValueError as exc: extra['held_source_reviews'].append({'notice_id': annotation['notice_id'], 'reason': str(exc)})
    try: checked = sum(fmt.recheck(row, native) for row in records)
    finally:
        if job['format'] == 'XLSX': native.close()
    if not records: raise ValueError('NO_SOURCE_RECORDS_NOT_A_COLLECTION_PASS')
    return records, nxt, checked, extra


def _state(ledger, job_id, page):
    reason = PREFIX+sha([job_id, page])
    row = ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=? ORDER BY seq DESC LIMIT 1", (reason,)).fetchone()
    return json.loads(row[0])['policy'] if row else None


def collect(ledger, registry, root, *, network=False):
    require_objective(registry)
    jobs = registry['global_sources']['collection_jobs']
    transport = Capture(Path(root)/'captures', network=network)
    current = {j['id']: j['url'] for j in jobs}; stopped = set(); report = []
    # Round-robin across source types: one industry's cursor cannot block others.
    for page in range(1, max(j['max_pages'] for j in jobs)+1):
        for job in jobs:
            if job['id'] in stopped or page > job['max_pages']: continue
            prior = _state(ledger, job['id'], page)
            if prior:
                report.append(prior); current[job['id']] = prior.get('next_url')
                if not current[job['id']]: stopped.add(job['id'])
                continue
            url = current[job['id']]
            if not url: stopped.add(job['id']); continue
            try: raw, receipt = transport.get(job['source_id'], url)
            except ValueError as exc:
                raw, receipt = None, {'status': 'CACHE_OR_SOURCE_GUARD_FAILED', 'url': url, 'error_type': str(exc)}
            if receipt['status'] in {'BATCH_LIMIT_PENDING', 'NOT_FETCHED_OFFLINE'}:
                report.append({'job_id': job['id'], 'page': page, 'status': receipt['status'], 'next_url': url}); stopped.add(job['id']); continue
            policy = {'job_id': job['id'], 'source_id': job['source_id'], 'page': page, 'url': url, 'http_status': receipt['status'], 'records': 0, 'stored': 0, 'exact_fields_checked': 0, 'next_url': None}
            if raw is None:
                policy.update(status='BLOCKED', reason=receipt.get('error_type', str(receipt['status'])), retry=False)
            else:
                try:
                    records, nxt, checked, extra = parse(raw, receipt, job)
                    if nxt:
                        fmt.safe_url(job['source_id'], nxt)
                        a, b = dict(parse_qsl(urlsplit(job['url']).query)), dict(parse_qsl(urlsplit(nxt).query))
                        for k, v in a.items():
                            if k not in {'page', 'offset', 'cursor', 'format'} and b.get(k) != v: raise ValueError('PAGINATION_SCOPE_CHANGED')
                    stored = fmt.save(ledger, records) if job['archive_facts'] else {'added': 0}
                    policy.update(status='FACTS_STORED' if job['archive_facts'] else 'PARSE_VALIDATED_RIGHTS_HOLD', records=len(records), stored=stored['added'], exact_fields_checked=checked, next_url=nxt, source_hash=sha(raw), tables=extra, native_source_in_remote_capsule=False, proof_scope='SCALAR_VALUES_AND_LOCATORS_NOT_INDEPENDENT_EVENT_MEANING', limits=job['semantic_limits'])
                except Exception as exc:
                    policy.update(status='BLOCKED', reason=type(exc).__name__+':'+str(exc)[:180], retry=False)
            with ledger.db:
                ledger.event('QUANTITATIVE_VALIDATION', {'reason': PREFIX+sha([job['id'], page]), 'originals_modified': False, 'policy': policy})
            report.append(policy); current[job['id']] = policy.get('next_url')
            if not current[job['id']]: stopped.add(job['id'])
    all_records = [json.loads(p) for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=?', (fmt.KIND,))]
    by = {}
    for source in sorted({r['source_id'] for r in all_records}):
        rows = [r for r in all_records if r['source_id'] == source]
        by[source] = {'record_versions': len(rows), 'unique_records': len({r['logical_id'] for r in rows}), 'numeric_fields': sum(sum(k in fmt.NUMERIC for k in r['claims']) for r in rows), 'kinds': dict(Counter(r['record_kind'] for r in rows)), 'published_at_unknown': sum(r['published_at'] == 'UNKNOWN' for r in rows)}
    handoff = fmt.q2_review_inputs(all_records)
    result = stamp_export({'plan_id': 'BCT-V4-Q-1.0', 'version': fmt.VERSION, 'pages': report, 'by_source': by, 'HTTP_requests_this_batch': transport.calls, 'bindings': bindings(), 'record_versions_total': len(all_records), 'unique_records_total': len({r['logical_id'] for r in all_records}), 'native_originals_archived': 0, 'confirmed_new_physical_orders': 0, 'qualified_supply_records': 0, 'Q2_signed_contract_review_inputs': handoff['signed_contract_records'], 'Q3_pairs': 0, 'S2': 0, 'S3': 0, 'AI_calls': 0, 'CPU_windows': 0})
    Path(root).mkdir(parents=True, exist_ok=True); (Path(root)/'q2-review-inputs.json').write_text(json.dumps(handoff, indent=2)+'\n')
    Path(root).mkdir(parents=True, exist_ok=True); (Path(root)/'collection-report.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--ledger', default=str(ROOT/'ledger')); parser.add_argument('--root', default=str(ROOT)); parser.add_argument('--network', action='store_true')
    a = parser.parse_args(); ledger = Ledger(a.ledger)
    try:
        with ledger.worker(): result = collect(ledger, json.loads(REG.read_text()), a.root, network=a.network)
        print('BCT_OFFICIAL_SOURCE_REPORT_JSON='+json.dumps(result))
    finally: ledger.close()


if __name__ == '__main__': main()
