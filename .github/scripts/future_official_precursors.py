"""One bounded manual collection using BCT's existing acquisition and body cache."""
import argparse
import base64
import importlib.util
import shutil
import subprocess
import tempfile
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, build_opener
from datetime import datetime, timezone
from collections import Counter

from bct.future_bottleneck import PublicRedirect, public_url
from bct.future_body import acquire_document, read_cached_body, extract_document, _Document, _nodes, _text, _CHALLENGE, _PREVIEW
from bct.future_github import GitHubTransport


def manifest_at(path):
    manifest = json.loads(Path(path).read_text())
    documents = manifest['documents']
    if len(documents) != 21 or len({d['url'] for d in documents}) != 21:
        raise ValueError('exactly 21 unique frozen URLs required')
    if any(not d.get('official_document') or not d.get('required_roles') for d in documents):
        raise ValueError('official document and needed role required')
    extra = manifest.get('supplemental_documents', [])
    target_scope = {'us-ghost-r-geo-isr', 'us-lng-liquefaction', 'us-defense-qualified-tungsten'}
    if len(extra) > 24 or any(d.get('target_id') not in target_scope or not d.get('official_document') or not d.get('required_roles') or d.get('host') != urlsplit(d['url']).hostname for d in extra):
        raise ValueError('only bounded official documents for three existing targets allowed')
    if set(manifest.get('collection_target_ids', [])) - target_scope:
        raise ValueError('collection target outside three existing targets')
    if len({d['url'] for d in documents + extra}) != len(documents + extra):
        raise ValueError('duplicate supplemental source')
    if set(manifest['allowed_domains']) != {urlsplit(d['url']).hostname for d in documents + extra}:
        raise ValueError('domain scope mismatch')
    from bct import future_body
    if hashlib.sha256(Path(future_body.__file__).read_bytes()).hexdigest() != manifest['extractor_sha256']:
        raise ValueError('existing extractor changed')
    if not re.fullmatch(r'[a-f0-9]{64}', manifest['objective_sha256']):
        raise ValueError('objective hash required')
    return manifest


def fetch(url, domains):
    """Keep BCT public-IP/redirect/TLS guards; retain response metadata."""
    if urlsplit(url).hostname not in domains:
        raise ValueError('source domain outside frozen manifest')
    public_url(url)

    class ScopedRedirect(PublicRedirect):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlsplit(newurl).hostname not in domains:
                raise ValueError('redirect domain outside frozen manifest')
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    request = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; BottleneckControlTower/0.1)',
        'Accept': 'text/html,application/xhtml+xml'})
    with build_opener(ScopedRedirect()).open(request, timeout=8) as response:
        payload = response.read(2_000_001)
        result = {'status': response.status, 'final_url': response.geturl(),
                  'content_type': response.headers.get_content_type()}
        if len(payload) > 2_000_000:
            return {**result, 'blocked_reason': 'BODY_TOO_LARGE'}
        if result['content_type'] == 'application/pdf' or payload.startswith(b'%PDF'):
            parsed = pdf_text_layer(payload)
            if parsed.get('blocked_reason') == 'PDF_TEXT_PARSER_NOT_INSTALLED':
                parsed['pending_pdf_base64'] = base64.b64encode(payload).decode()
                parsed['download_sha256'] = hashlib.sha256(payload).hexdigest()
            return {**result, **parsed}
        result['html'] = payload.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
        return result



def pdf_text_layer(payload):
    """Use retained Poppler only; never install a parser or invoke OCR."""
    parser = shutil.which('pdftotext')
    if not parser:
        return {'blocked_reason': 'PDF_TEXT_PARSER_NOT_INSTALLED'}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'source.pdf'
        path.write_bytes(payload)
        try:
            result = subprocess.run([parser, '-layout', '-enc', 'UTF-8', str(path), '-'],
                                    capture_output=True, timeout=20)
            if result.returncode:
                return {'blocked_reason': 'PDF_TEXT_PARSER_FAILED'}
            body = result.stdout.decode('utf-8').strip()
            if not re.search(r'\w', body):
                return {'blocked_reason': 'PDF_NO_TEXT_LAYER'}
            info = {}
            if shutil.which('pdfinfo'):
                inspected = subprocess.run(['pdfinfo', str(path)], capture_output=True, timeout=10)
                for line in inspected.stdout.decode('utf-8', errors='replace').splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        if key in ('Pages', 'CreationDate', 'ModDate', 'Title', 'Encrypted'):
                            info[key] = value.strip()
            return {'body': body, 'body_status': 'PARTIAL',
                    'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
                    'body_chars': len(body), 'extraction_method': 'OFFICIAL_PDF_TEXT_LAYER',
                    'reasons': ['PDF_VISUAL_AND_TABLE_COMPLETENESS_UNVERIFIED'],
                    'completeness': {'assessment': 'ACCESSIBLE_TEXT_LAYER_ONLY', 'OCR_used': False},
                    'pdf_metadata': info, 'download_sha256': hashlib.sha256(payload).hexdigest()}
        except (subprocess.TimeoutExpired, UnicodeError):
            return {'blocked_reason': 'PDF_TEXT_PARSER_TIMEOUT_OR_ENCODING'}


def html_structure(html, source_url):
    parsed = _Document(); parsed.feed(html); parsed.close()
    nodes = list(_nodes(parsed.root))
    containers = [{'tag': n.tag, 'id': n.attrs.get('id'), 'class': n.attrs.get('class'),
                   'role': n.attrs.get('role'), 'chars': len(_text(n)), 'closed': n.closed}
                  for n in nodes if n.tag in ('article', 'main') or
                  any(re.search(r'article|story|content|release|main', str(n.attrs.get(k, '')), re.I)
                      for k in ('id', 'class', 'role'))]
    links = [{'url': urljoin(source_url, n.attrs['href']), 'label': _text(n)}
             for n in nodes if n.tag == 'a' and n.attrs.get('href') and
             urlsplit(urljoin(source_url, n.attrs['href'])).hostname == urlsplit(source_url).hostname]
    document_links = [{'url': urljoin(source_url, n.attrs['href']), 'label': _text(n)}
                      for n in nodes if n.tag == 'a' and n.attrs.get('href') and
                      (re.search(r'\.(?:pdf|xlsx?)(?:[?#]|$)|/Archives/|/download/', n.attrs['href'], re.I))]
    scripts = [{'type': n.attrs.get('type'), 'id': n.attrs.get('id'),
                'chars': len(_text(n, include_script=True))} for n in nodes if n.tag == 'script']
    return {'containers': containers[:80], 'same_origin_links': links[:150], 'scripts': scripts[:40], 'document_links': document_links[:100]}



def official_html_fallback(html, source_url):
    """Recover only the observed public publisher article container, no JS/OCR."""
    if urlsplit(source_url).hostname != 'news.northropgrumman.com':
        return None
    parsed = _Document(); parsed.feed(html); parsed.close()
    nodes = list(_nodes(parsed.root))
    node = next((n for n in nodes if n.attrs.get('id') == 'articleBody'), None)
    if node is None or not node.closed:
        return None
    visible = _text(node)
    if not visible or _CHALLENGE.search(visible) or _PREVIEW.search(visible):
        return None
    headings = [_text(n) for n in nodes if n.tag == 'h1' and 'headline' in str(n.attrs.get('class', ''))]
    dates = [_text(n) for n in nodes if 'PublishDateText' in str(n.attrs.get('class', ''))]
    body = '\n'.join([*headings[:1], *dates[:1], visible])
    return {'body': body, 'body_status': 'PARTIAL',
            'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'body_chars': len(body), 'extraction_method': 'OFFICIAL_ARTICLE_ID_TEXT',
            'reasons': ['OFFICIAL_DIV_BODY_STRUCTURE_UNVERIFIED'],
            'completeness': {'explicit_body_scope': True, 'body_scope_closed': True,
                             'assessment': 'ACCESSIBLE_STRUCTURE_ONLY', 'captured_table_rows': 0},
            'rendered_publication_date': dates[0] if dates else 'UNKNOWN'}

def read_snapshot(transport, path):
    if not re.fullmatch(r'official-precursors/actions-[0-9]+-[0-9]+(?:-pdf-resolved)?\.json', path):
        raise ValueError('approved immutable snapshot path required')
    value = transport.requester('GET', '/contents/' + path + '?ref=future-bottleneck-data')
    sha = value['sha']
    if value.get('encoding') != 'base64':
        value = transport.requester('GET', '/git/blobs/' + sha)
    raw = base64.b64decode(value['content'])
    if hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() != sha:
        raise ValueError('prior snapshot SHA mismatch')
    return json.loads(raw)

def publication_dates(html):
    # Candidates only: no inferred dates from paths, collection time or headers.
    dates = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', html)
    dates += re.findall(r'<meta[^>]+(?:property|name)=["\x27](?:article:published_time|DC.date.issued)["\x27][^>]+content=["\x27]([^"\x27]+)', html, re.I)
    return sorted(set(dates))


def collect(manifest, output, cache_dir, *, fetcher=fetch, run_id='LOCAL', prior=None):
    binding = {k: manifest[k] for k in ('objective_version', 'objective_sha256')}
    documents, responses = [], []
    domains = set(manifest['allowed_domains'])
    prior_by_url = {d['url']: d for d in (prior or {}).get('documents', [])}
    # First perform the bounded HTTP trial. Never substitute another URL/source.
    for source in manifest['documents'] + manifest.get('supplemental_documents', []):
        at = datetime.now(timezone.utc).isoformat()
        old = prior_by_url.get(source['url'])
        if old and not source.get('refresh_locator', False) and (source['target_id'] not in manifest.get('collection_target_ids', [source['target_id']]) or not (old.get('http_status') == 200 and old.get('body_status') == 'BLOCKED')):
            responses.append((source, at, {'reused_record': old}))
            continue
        try:
            response = fetcher(source['url'], domains)
        except Exception as exc:
            response = {'error': type(exc).__name__, 'blocked_reason': 'NETWORK_ACCESS_FAILED',
                        'status': exc.code if isinstance(exc, HTTPError) else None,
                        'final_url': exc.geturl() if isinstance(exc, HTTPError) else None,
                        'content_type': exc.headers.get_content_type() if isinstance(exc, HTTPError) and exc.headers else None}
        responses.append((source, at, response))
    # Extract only responses actually received, with unchanged BCT acquisition.
    for source, at, response in responses:
        if 'reused_record' in response:
            record = dict(response['reused_record'])
            record['reused_from_run'] = prior['run_id']
            documents.append(record)
            continue
        document_id = 'official-' + hashlib.sha256(source['url'].encode()).hexdigest()
        record = {'document_id': document_id, 'original_url': source['url'],
                  'url': source['url'], 'final_url': response.get('final_url'),
                  'source_domain': source['host'], 'target_id': source['target_id'],
                  'target': source['target'], 'source_organization': source['organization'],
                  'required_roles': source['required_roles'], 'locator_only': source.get('locator_only', False), 'decisive_unknown': source.get('decisive_unknown'), 'collected_at': at,
                  'publication_timestamp': 'UNKNOWN', 'http_status': response.get('status'),
                  'content_type': response.get('content_type'), 'body': '',
                  'body_sha256': None, 'body_status': 'BLOCKED',
                  'independence_verified': False, 'original_source': True}
        record['response_structure'] = html_structure(response['html'], source['url']) if response.get('html') else None
        record['pdf_metadata'] = response.get('pdf_metadata')
        record['download_sha256'] = response.get('download_sha256')
        if response.get('pending_pdf_base64'):
            record['pending_pdf_base64'] = response['pending_pdf_base64']
        if response.get('blocked_reason'):
            record.update(blocked_reason=response['blocked_reason'], error=response.get('error'))
        else:
            fetched = response
            fallback = None
            if response.get('html'):
                existing = extract_document(response['html'], http_status=response.get('status', 200), content_type=response.get('content_type', 'text/html'))
                if not existing['body'] and existing['reasons'] in (['NO_ARTICLE_CONTENT'], ['NO_READABLE_BODY']):
                    fallback = official_html_fallback(response['html'], source['url'])
                    if fallback:
                        fetched = fallback
                        record['rendered_publication_date'] = fallback['rendered_publication_date']
            acquired = acquire_document(source['url'], 'official-source-v1', None,
                                        cache_dir, lambda url: fetched,
                                        trigger='USER', trigger_id=run_id, now=at)
            record.update(acquired['metadata'], body=acquired['body'], acquisition_ledger=acquired['ledger'])
            if not record['body']:
                record['body_status'] = 'BLOCKED'
                record['blocked_reason'] = 'NO_READABLE_BODY_WITH_EXISTING_EXTRACTOR'
            else:
                assert read_cached_body(cache_dir, record['body_sha256']) == record['body']
            dates = publication_dates(response.get('html', ''))
            record['publication_timestamp_candidates'] = dates
            if len(dates) == 1:
                record['publication_timestamp'] = dates[0]
                record['publication_verification'] = 'SOURCE_HTML_METADATA_REQUIRES_REVIEW'
        documents.append(record)
    snapshot = {'format': 'bct-official-precursor-snapshot-v1', **binding,
                'run_id': run_id, 'extractor_sha256': manifest['extractor_sha256'],
                'manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                'documents': documents, 'summary': dict(Counter(d['body_status'] for d in documents)),
                'operating_records_modified': False, 'raw_html_retained': False}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return snapshot



def resolve_pending_pdf(snapshot, cache_dir):
    """Resolve an Actions download with an already installed local text parser."""
    if not shutil.which('pdftotext'):
        raise ValueError('PDF_TEXT_PARSER_NOT_INSTALLED')
    snapshot = json.loads(json.dumps(snapshot))
    for record in snapshot['documents']:
        encoded = record.pop('pending_pdf_base64', None)
        if not encoded:
            continue
        payload = base64.b64decode(encoded, validate=True)
        if len(payload) > 2_000_000 or hashlib.sha256(payload).hexdigest() != record.get('download_sha256'):
            raise ValueError('pending PDF download hash mismatch')
        extracted = pdf_text_layer(payload)
        if extracted.get('blocked_reason'):
            record['blocked_reason'] = extracted['blocked_reason']
            continue
        acquired = acquire_document(record['url'], 'official-source-v1', record.get('acquisition_ledger'),
                                    cache_dir, lambda url: extracted, trigger='USER',
                                    trigger_id='PDF_TEXT_LAYER_' + snapshot['run_id'])
        record.update(acquired['metadata'], body=acquired['body'], acquisition_ledger=acquired['ledger'],
                      pdf_metadata=extracted.get('pdf_metadata'), pdf_resolution='EXISTING_WORKSPACE_PDFTOTEXT',
                      resolved_at=datetime.now(timezone.utc).isoformat())
        record.pop('blocked_reason', None)
        assert read_cached_body(cache_dir, record['body_sha256']) == record['body']
    snapshot['summary'] = dict(Counter(d['body_status'] for d in snapshot['documents']))
    snapshot['resolved_from_run_id'] = snapshot['run_id']
    return snapshot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--prior-snapshot')
    parser.add_argument('--resolve-pdf-snapshot', type=Path)
    args = parser.parse_args()
    manifest = manifest_at(args.manifest)
    if args.resolve_pdf_snapshot:
        prior = json.loads(args.resolve_pdf_snapshot.read_text())
        if any(prior.get(k) != manifest.get(k) for k in ('objective_version', 'objective_sha256', 'extractor_sha256')):
            raise ValueError('PDF snapshot objective/extractor mismatch')
        snapshot = resolve_pending_pdf(prior, args.cache_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
        if args.publish:
            transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
            path = 'official-precursors/' + snapshot['run_id'] + '-pdf-resolved.json'
            print(json.dumps({'snapshot_path': path, 'blob_sha': transport.write(path, snapshot, None)}))
        return
    run_id = 'actions-' + os.environ.get('GITHUB_RUN_ID', 'LOCAL') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN']) if args.publish or args.prior_snapshot else None
    prior = read_snapshot(transport, args.prior_snapshot) if args.prior_snapshot else None
    if prior and any(prior.get(k) != manifest.get(k) for k in ('objective_version', 'objective_sha256', 'extractor_sha256')):
        raise ValueError('prior objective/extractor mismatch')
    snapshot = collect(manifest, args.output, args.cache_dir, run_id=run_id, prior=prior)
    snapshot['pdf_parser_installed'] = bool(shutil.which('pdftotext'))
    snapshot['pdf_parser_capabilities'] = {
        'commands': {name: bool(shutil.which(name)) for name in ('pdftotext', 'pdfinfo', 'pdf2txt.py', 'mutool', 'gs')},
        'python_modules': {name: bool(importlib.util.find_spec(name)) for name in ('pypdf', 'PyPDF2', 'pdfminer', 'fitz')}}
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(snapshot['summary']))
    if args.publish:
        # Create once, conditional GitHub contents write. Never overwrite live sidecars.
        transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
        path = 'official-precursors/' + run_id + '.json'
        sha = transport.write(path, snapshot, None)
        print(json.dumps({'snapshot_path': path, 'blob_sha': sha}))


if __name__ == '__main__':
    main()
