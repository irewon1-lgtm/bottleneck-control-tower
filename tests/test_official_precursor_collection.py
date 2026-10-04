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
    assert snapshot['summary'] == {'BLOCKED': 1, 'FULL': 20}
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
    assert result['summary'] == {'BLOCKED': 21}
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
