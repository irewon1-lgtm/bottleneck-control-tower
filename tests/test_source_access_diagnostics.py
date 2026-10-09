import socket
import ssl
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
import pytest
from bct.future_body import access_failure, acquire_document


@pytest.mark.parametrize('exc,category,state', [
    (socket.gaierror(socket.EAI_AGAIN, 'temporary'), 'DNS_RESOLUTION_FAILED', 'SOURCE_WAIT'),
    (URLError(socket.gaierror(socket.EAI_NONAME, 'missing')), 'DNS_RESOLUTION_FAILED', 'SOURCE_WAIT'),
    (ssl.SSLError('certificate'), 'TLS_FAILED', 'SOURCE_BLOCKED'),
    (TimeoutError(), 'TIMEOUT', 'SOURCE_WAIT'),
    (HTTPError('https://example.test', 403, 'Forbidden', {}, None), 'HTTP_403', 'SOURCE_BLOCKED'),
    (HTTPError('https://example.test', 404, 'Not found', {}, None), 'HTTP_404', 'UNAVAILABLE'),
    (HTTPError('https://example.test', 429, 'Limited', {'Retry-After':'90'}, None), 'HTTP_429', 'SOURCE_WAIT'),
    (TypeError('bad adapter'), 'COLLECTOR_ERROR', 'ERROR'),
    (IncompleteRead(b'partial response',100), 'CONNECTION_INTERRUPTED', 'SOURCE_WAIT'),
])
def test_diagnostic_is_bound_to_real_failure(exc, category, state, tmp_path):
    diagnostic = access_failure(exc)
    assert diagnostic['category'] == category and diagnostic['state'] == state
    def fail(_):raise exc
    result = acquire_document('https://example.test', 'v1', {}, tmp_path, fail)
    assert result['metadata']['access_diagnostic'] == diagnostic
    assert result['body'] == '' and result['metadata']['body_status'] == 'UNAVAILABLE'
    assert result['ledger']['versions']['v1']['history'][-1]['access_diagnostic'] == diagnostic


def test_partial_cache_survives_dns_without_becoming_full(tmp_path):
    original = acquire_document('https://example.test', 'v1', {}, tmp_path,
                                lambda _: '<article><p>Introduction.</p></article><p>Sign in to continue</p>')
    def fail(_):raise socket.gaierror(socket.EAI_AGAIN, 'temporary')
    result = acquire_document('https://example.test', 'v1', original['ledger'], tmp_path, fail,
                              trigger='SCHEDULED', trigger_id='changed-runner')
    assert result['body'] == original['body'] and result['metadata']['body_status'] == 'PARTIAL'
    assert result['metadata']['access_diagnostic']['category'] == 'DNS_RESOLUTION_FAILED'


def test_truncated_http_response_cannot_become_full_even_with_closed_article(tmp_path):
    result = acquire_document('https://example.test', 'v1', {}, tmp_path, lambda _:
        {'html':'<article><p>Complete visible article.</p></article>', 'truncated':True})
    assert result['metadata']['body_status']=='PARTIAL'
    assert 'BODY_DOWNLOAD_TRUNCATED' in result['metadata']['reasons']


def test_fetcher_reads_large_templates_and_marks_its_hard_limit(monkeypatch):
    from bct import future_bottleneck as collector
    from email.message import Message
    monkeypatch.setattr(collector, 'public_url', lambda _:None)
    headers=Message();headers['Content-Type']='text/html; charset=utf-8'
    class Response:
        status=200
        def __init__(self,data):self.data=data;self.headers=headers
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,maximum):return self.data[:maximum]
    class Opener:
        def open(self,*args,**kwargs):return Response(data)
    monkeypatch.setattr(collector,'build_opener',lambda *args:Opener())
    data=b'x'*(2_000_000+100)
    assert collector.fetch_html('https://example.test')['truncated'] is False
    data=b'x'*(8*1024*1024+1)
    fetched=collector.fetch_html('https://example.test')
    assert fetched['truncated'] is True and len(fetched['html'])==8*1024*1024
