import json
from datetime import datetime, timedelta, timezone

import pytest

from bct.future_body import acquire_document, cache_body, extract_document, public_metadata, read_cached_body


def test_short_structurally_complete_official_article_is_full():
    result = extract_document('<nav><p>Home News Subscribe</p></nav><article><h1>Plant update</h1><p>The reactor will close in 2028.</p></article>')
    assert result['body_status'] == 'FULL'
    assert 'reactor will close' in result['body']
    assert 'Subscribe' not in result['body']
    assert result['body_chars'] < 100
    assert result['completeness']['body_scope_closed']


@pytest.mark.parametrize('html,status,reason', [
    ('<nav><p>News Investors Contact Subscribe</p></nav>', 200, 'NO_READABLE_BODY'),
    ('<title>Just a moment</title><p>Enable javascript and cookies</p>', 200, 'ACCESS_CHALLENGE'),
    ('<article><p>Real-looking preview.</p></article>', 403, 'HTTP_403'),
    ('<article><h1>News</h1></article>', 200, 'NO_ARTICLE_CONTENT'),
])
def test_menu_challenge_or_http_block_is_unavailable(html, status, reason):
    result = extract_document(html, http_status=status)
    assert result['body_status'] == 'UNAVAILABLE'
    assert result['body'] == ''
    assert reason in result['reasons']


def test_preview_is_partial_and_hidden_jsonld_does_not_replace_it():
    html = '<article><h1>Output</h1><p>Production is delayed.</p><p>Subscribe to continue reading.</p></article>'
    html += '<script type="application/ld+json">' + json.dumps({'@type': 'NewsArticle', 'articleBody': 'Subscriber-only complete text.', 'isAccessibleForFree': False}) + '</script>'
    result = extract_document(html)
    assert result['body_status'] == 'PARTIAL'
    assert 'PAYWALL_OR_LOGIN_PREVIEW' in result['reasons']
    assert 'Subscriber-only' not in result['body']


def test_lists_headings_and_complete_table_are_readable():
    result = extract_document('<main><h1>Capacity</h1><p>Table 1 shows qualified slots.</p><ul><li>Certified by 2027</li></ul><table><caption>Table 1</caption><tr><th>Year</th><th>Units</th></tr><tr><td>2028</td><td>20</td></tr></table></main>')
    assert result['body_status'] == 'FULL'
    assert 'Certified by 2027' in result['body']
    assert '2028 | 20' in result['body']
    assert result['completeness']['captured_table_rows'] == 2


@pytest.mark.parametrize('html,reason', [
    ('<article><p>Table below compares demand and capacity.</p><table><img src="table.png"></table></article>', 'MISSING_TABLE_CONTENT'),
    ('<article><p>See table 1 for the required quantities.</p></article>', 'MISSING_TABLE_CONTENT'),
    ('<article><p>Orders are growing.</p>', 'TRUNCATED_BODY_STRUCTURE'),
    ('<div class="article-body"><p class="excerpt">Production will stop.</p></div>', 'PREVIEW_OR_SUMMARY_CONTENT'),
    ('<p>Only a paragraph without a verifiable article scope.</p>', 'UNVERIFIED_BODY_SCOPE'),
])
def test_missing_or_incomplete_content_is_partial(html, reason):
    result = extract_document(html)
    assert result['body_status'] == 'PARTIAL'
    assert result['body']
    assert reason in result['reasons']


def test_jsonld_article_and_body_div_are_supported():
    ld = '<script type="application/ld+json">' + json.dumps({'@graph': [{'@type': 'NewsArticle', 'articleBody': 'A signed contract needs qualified supply in 2028.'}]}) + '</script>'
    assert extract_document(ld)['body_status'] == 'FULL'
    result = extract_document('<div class="story-body"><p>Production begins in 2028.</p></div><aside><article><p>Ignore this advertisement.</p></article></aside>')
    assert result['body_status'] == 'FULL'
    assert 'advertisement' not in result['body']


def test_paywall_outside_article_blocks_jsonld_substitution():
    html = '<p class="paywall">Subscriber access required.</p><script type="application/ld+json">'
    html += json.dumps({'@type': 'NewsArticle', 'articleBody': 'Hidden entire article body.'}) + '</script>'
    result = extract_document(html)
    assert result['body_status'] == 'PARTIAL'
    assert 'Hidden entire' not in result['body']


def test_direct_extraction_adapter_and_filter_alias(tmp_path):
    first = acquire_document('https://example.org/a', 'v1', {}, tmp_path,
                             lambda u: {'body': 'Production stops in 2028.', 'status': 'FULL', 'extraction_method': 'TEST'})
    assert first['metadata']['body_status'] == 'FULL'
    again = acquire_document('https://example.org/a', 'v1', first['ledger'], tmp_path,
                             lambda u: pytest.fail('filter-only path must reuse cache'), trigger='FILTER_CHANGE')
    assert again['cache_reused'] and again['body'] == first['body']


def test_cache_is_checked_and_public_metadata_never_defaults_to_full_text(tmp_path):
    result = extract_document('<article><p>Confidential redistribution rights are not granted.</p></article>')
    digest = cache_body(tmp_path, result['body'])
    assert read_cached_body(tmp_path, digest) == result['body']
    metadata = public_metadata(result)
    assert 'body' not in metadata
    assert metadata['cache_access'] == 'PRIVATE_RUNTIME'
    assert public_metadata(result, redistribution_allowed=True)['body'] == result['body']
    (tmp_path / (digest + '.txt')).write_text('corrupted')
    assert read_cached_body(tmp_path, digest) is None
    assert read_cached_body(tmp_path, '../secret') is None


def test_filter_change_reuses_cached_body_without_fetching(tmp_path):
    calls = []
    def fetch(url):
        calls.append(url)
        return '<article><p>Orders grow in 2028.</p></article>'
    first = acquire_document('https://example.org/a', 'v1', {}, tmp_path, fetch)
    again = acquire_document('https://example.org/a', 'v1', first['ledger'], tmp_path, fetch, trigger='FILTER_CHANGED')
    assert again['cache_reused'] and not again['acquired']
    assert again['body'] == first['body'] and len(calls) == 1
    assert again['ledger']['versions']['v1']['automatic_attempts'] == 1


def test_retry_limit_survives_time_and_explicit_checks_are_unique(tmp_path):
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    calls = []
    def fetch(url):
        calls.append(url)
        raise TimeoutError()
    ledger = {}
    for i in range(3):
        result = acquire_document('https://example.org/a', 'v1', ledger, tmp_path, fetch, now=start + timedelta(days=i))
        ledger = result['ledger']
    stopped = acquire_document('https://example.org/a', 'v1', ledger, tmp_path, fetch, now=start + timedelta(days=100))
    assert stopped['blocked'] == 'RETRY_LIMIT' and len(calls) == 3
    check = acquire_document('https://example.org/a', 'v1', stopped['ledger'], tmp_path, fetch, trigger='SCHEDULED', trigger_id='2027-01-check')
    assert check['acquired'] and len(calls) == 4
    duplicate = acquire_document('https://example.org/a', 'v1', check['ledger'], tmp_path, fetch, trigger='SCHEDULED', trigger_id='2027-01-check')
    assert duplicate['blocked'] == 'EXPLICIT_CHECK_ALREADY_USED' and len(calls) == 4
    assert duplicate['ledger']['versions']['v1']['automatic_attempts'] == 3
    assert len(duplicate['ledger']['versions']['v1']['history']) == 4
    with pytest.raises(ValueError):
        acquire_document('https://example.org/a', 'v1', {}, tmp_path, fetch, trigger='USER')


def test_partial_text_survives_failed_retry_and_source_change_retains_versions(tmp_path):
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    responses = iter(['<article><p>Table below has the supply numbers.</p></article>', TimeoutError(), '<article><p>Corrected demand: 20 units in 2028.</p></article>'])
    def fetch(url):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value
    partial = acquire_document('https://example.org/a', 'v1', {}, tmp_path, fetch, now=start)
    assert partial['metadata']['body_status'] == 'PARTIAL'
    failed = acquire_document('https://example.org/a', 'v1', partial['ledger'], tmp_path, fetch, now=start + timedelta(days=1))
    assert failed['body'] == partial['body']
    assert failed['metadata']['body_status'] == 'PARTIAL'
    assert failed['metadata']['acquisition_status'] == 'UNAVAILABLE'
    cached = acquire_document('https://example.org/a', 'v1', failed['ledger'], tmp_path, fetch, trigger='FILTER_CHANGED')
    assert cached['body'] == partial['body']
    changed = acquire_document('https://example.org/a', 'v2', failed['ledger'], tmp_path, fetch, now=start + timedelta(days=2))
    assert changed['metadata']['body_status'] == 'FULL'
    assert changed['metadata']['body_sha256'] != partial['metadata']['body_sha256']
    assert changed['ledger']['versions']['v1']['automatic_attempts'] == 2
    assert len(changed['ledger']['versions']['v1']['history']) == 2
    assert changed['ledger']['versions']['v2']['automatic_attempts'] == 1


def test_cooldown_does_not_consume_attempt_and_lost_cache_is_explicit(tmp_path):
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    first = acquire_document('https://example.org/a', 'v1', {}, tmp_path, lambda u: '<article><p>Table below is absent.</p></article>', now=start)
    due = acquire_document('https://example.org/a', 'v1', first['ledger'], tmp_path, lambda u: pytest.fail('cooldown must not fetch'), now=start + timedelta(minutes=1))
    assert due['blocked'] == 'RETRY_NOT_DUE' and due['cache_reused']
    assert due['ledger']['versions']['v1']['automatic_attempts'] == 1
    for path in tmp_path.iterdir():
        path.unlink()
    lost = acquire_document('https://example.org/a', 'v1', due['ledger'], tmp_path, lambda u: pytest.fail('filter change must not fetch'), trigger='FILTER_CHANGED')
    assert lost['blocked'] == 'CACHE_UNAVAILABLE' and not lost['cache_reused']
@pytest.mark.parametrize('html', [
    '<main><p>Verify you are human to view this article.</p></main>',
    '<title>Security Check</title><article><p>Access denied. Please verify you are human.</p></article>',
])
def test_challenge_inside_article_scope_is_not_full(html):
    result = extract_document(html)
    assert result['body_status'] == 'UNAVAILABLE'
    assert 'ACCESS_CHALLENGE' in result['reasons']


def test_normal_article_discussing_access_checks_remains_readable():
    result = extract_document('<article><h1>Factory access controls change</h1><p>The report discusses systems that verify you are human and the resulting certification delays.</p></article>')
    assert result['body_status'] == 'FULL'
