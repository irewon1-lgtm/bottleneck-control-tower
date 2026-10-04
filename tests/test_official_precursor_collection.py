import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('official_collector', ROOT / '.github/scripts/future_official_precursors.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_scope_rejects_extra_and_duplicate_urls(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    assert len(manifest['documents']) == 21
    manifest['documents'][1] = manifest['documents'][0]
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='unique'):
        module.manifest_at(path)


def test_mixed_batch_isolates_network_failure_and_preserves_body_hash(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    html = '<html><article><h1>Capacity plan</h1><p>Qualification trials begin in 2027.</p></article></html>'
    failed = manifest['documents'][0]['url']
    def fixture(url, domains):
        assert domains == set(manifest['allowed_domains'])
        if url == failed:
            raise TimeoutError()
        return {'html': html, 'status': 200, 'final_url': url, 'content_type': 'text/html'}
    snapshot = module.collect(manifest, tmp_path / 'snapshot.json', tmp_path / 'cache', fetcher=fixture)
    assert snapshot['summary'] == {'BLOCKED': 1, 'FULL': 22}
    for doc in snapshot['documents'][1:]:
        assert doc['body_sha256'] == hashlib.sha256(doc['body'].encode()).hexdigest()
        assert module.read_cached_body(tmp_path / 'cache', doc['body_sha256']) == doc['body']
    assert snapshot['documents'][0]['publication_timestamp'] == 'UNKNOWN'
    assert not snapshot['raw_html_retained']


def test_pdf_is_not_treated_as_readable_body(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    def fixture(url, domains):
        return {'status': 200, 'final_url': url, 'content_type': 'application/pdf',
                'blocked_reason': 'EXISTING_HTML_EXTRACTOR_DOES_NOT_SUPPORT_PDF'}
    result = module.collect(manifest, tmp_path / 'snapshot.json', tmp_path / 'cache', fetcher=fixture)
    assert result['summary'] == {'BLOCKED': 23}
    assert all(d['body_sha256'] is None for d in result['documents'])


def test_manifest_rejects_changed_extractor(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    manifest['extractor_sha256'] = '0' * 64
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='extractor changed'):
        module.manifest_at(path)


def test_redirect_outside_fixed_domains_is_rejected(monkeypatch):
    monkeypatch.setattr(module, 'public_url', lambda u: None)
    class Opener:
        def __init__(self, handler): self.handler = handler
        def open(self, request, timeout):
            return self.handler.redirect_request(request, None, 302, '', {}, 'https://outside.invalid/doc')
    monkeypatch.setattr(module, 'build_opener', lambda handler: Opener(handler))
    with pytest.raises(ValueError, match='redirect domain'):
        module.fetch('https://www.energy.gov/doc', {'www.energy.gov'})


def test_http_error_retains_response_metadata(tmp_path):
    from email.message import Message
    from urllib.error import HTTPError
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    headers = Message()
    headers['Content-Type'] = 'text/html; charset=utf-8'
    def fixture(url, domains):
        raise HTTPError(url, 403, 'Forbidden', headers, None)
    result = module.collect(manifest, tmp_path / 'snapshot.json', tmp_path / 'cache', fetcher=fixture)
    assert result['summary'] == {'BLOCKED': 23}
    assert all(d['http_status'] == 403 and d['content_type'] == 'text/html' and d['final_url'] == d['url'] for d in result['documents'])


def test_recovery_reuses_success_and_does_not_retry_denials(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    prior = {'run_id': 'prior', 'documents': [
        {'url': d['url'], 'http_status': 403, 'body_status': 'BLOCKED', 'body': ''}
        for d in manifest['documents'] + manifest.get('supplemental_documents', [])]}
    prior['documents'][0]['http_status'] = 200
    calls = []
    def fixture(url, domains):
        calls.append(url)
        return {'html': '<article><p>Public source text.</p></article>', 'status': 200,
                'final_url': url, 'content_type': 'text/html'}
    result = module.collect(manifest, tmp_path / 'snapshot.json', tmp_path / 'cache',
                            fetcher=fixture, prior=prior)
    assert calls == [manifest['documents'][0]['url']]
    assert result['summary'] == {'FULL': 1, 'BLOCKED': 22}
    assert all(d.get('reused_from_run') == 'prior' for d in result['documents'][1:])


def test_pdf_text_layer_parser_without_ocr():
    import shutil
    if not shutil.which('pdftotext'):
        pytest.skip('existing PDF parser unavailable')
    stream = b'BT /F1 12 Tf 72 720 Td (Actual public PDF text.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    payload = b'%PDF-1.4\n'; offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(payload)); payload += str(index).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    xref = len(payload)
    payload += b'xref\n0 6\n0000000000 65535 f \n'
    payload += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    payload += b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'
    result = module.pdf_text_layer(payload)
    assert 'Actual public PDF text.' in result['body']
    assert result['body_status'] == 'PARTIAL'
    assert result['completeness']['OCR_used'] is False
    assert result['body_sha256'] == hashlib.sha256(result['body'].encode()).hexdigest()


def test_no_installed_pdf_parser_is_blocked(monkeypatch):
    monkeypatch.setattr(module.shutil, 'which', lambda name: None)
    assert module.pdf_text_layer(b'%PDF') == {'blocked_reason': 'PDF_TEXT_PARSER_NOT_INSTALLED'}


def test_observed_official_div_fallback_preserves_source_text_and_partial():
    html = '<h1 class="headline">Satellite prototype</h1><p class="NewsroomArticleBody_PublishDateText">September 18, 2026</p><div id="articleBody"><div>Flight-proven platform.</div></div>'
    result = module.official_html_fallback(html, 'https://news.northropgrumman.com/satellites/source')
    assert result['body'] == 'Satellite prototype\nSeptember 18, 2026\nFlight-proven platform.'
    assert result['body_status'] == 'PARTIAL'
    assert result['rendered_publication_date'] == 'September 18, 2026'
    assert module.official_html_fallback(html, 'https://outside.invalid/source') is None


def test_fallback_does_not_read_challenge_or_login_preview():
    for text in ('Verify you are human', 'Sign in to continue reading'):
        html = '<div id="articleBody">' + text + '</div>'
        assert module.official_html_fallback(html, 'https://news.northropgrumman.com/source') is None


def test_supplement_does_not_allow_new_targets(tmp_path):
    manifest = module.manifest_at(ROOT / '.github/official-precursor-urls.json')
    manifest['supplemental_documents'][0]['target_id'] = 'unrelated-target'
    path = tmp_path / 'manifest.json'; path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='already identified LNG'):
        module.manifest_at(path)
