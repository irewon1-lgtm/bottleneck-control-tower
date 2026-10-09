import socket
import ssl
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
