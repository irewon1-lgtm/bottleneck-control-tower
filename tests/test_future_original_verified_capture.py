"""Real original-source capture now produces body-version-bound proofs."""
import json
from datetime import datetime, timezone

import pytest

from bct import future_bottleneck as fb
from bct.future_body import acquire_document, verified_source_metadata, extract_document


URL='https://example.org/news/verified-a'
BODY='The qualified lithium battery cell capacity will increase in 2028 as customers add orders to their factories.'

def html(*, published=True, canonical=True, reprint=False):
    return ('<html><head>'
            + ('<link rel="canonical" href="'+URL+'">' if canonical else '')
            + '<meta property="og:site_name" content="Example Materials Journal">'
            + ('<meta property="article:published_time" content="2026-11-13T01:00:00+00:00">' if published else '')
            + '<script type="application/ld+json">'
            + json.dumps({'@type':'NewsArticle','@id':URL,'url':URL,
                           'publisher':{'name':'Example Materials Journal'},
                           **({'datePublished':'2026-11-13T01:00:00+00:00'} if published else {})})
            + '</script></head><body><article><h1>Verified supply news</h1><p>'
            + BODY
            + (' Originally published by Reuters.' if reprint else '')
            + '</p></article></body></html>')


def response(text=None, *, final_url=URL, truncated=False, status=200):
    raw=(text if text is not None else html()).encode()
    return {'html':raw.decode(),'raw':raw,'final_url':final_url,'status':status,
            'content_type':'text/html','truncated':truncated}


def test_real_publisher_proof_is_bound_to_body_and_survives_source_storage(monkeypatch,tmp_path):
    monkeypatch.setattr(fb,'fetch_capture',lambda url:response())
    observed=fb.fetch_html(URL)
    assert 'raw' not in observed and 'final_url' not in observed
    assert observed['provenance_verified'] and observed['publication_verified']
    digest=extract_document(observed['html'])['body_sha256']
    assert observed['provenance_evidence']['body_sha256']==digest
    assert observed['publication_evidence']['body_sha256']==digest
    first=acquire_document(URL,'f1',{},tmp_path,lambda url:observed)
    assert first['metadata']['body_status']=='FULL'
    assert first['metadata']['provenance_verified'] is True
    assert first['metadata']['publication_verified'] is True
    assert verified_source_metadata(first['metadata'],digest)['provenance_verified'] is True
    assert verified_source_metadata(first['metadata'],digest)['published_at'].startswith('2026-11-13')
    assert verified_source_metadata(first['metadata'],'0'*64)=={}


@pytest.mark.parametrize("change",[
    {'canonical':False},
    {'published':False},
    {'reprint':True},
])
def test_unverified_source_is_never_promoted_even_if_body_full(monkeypatch,change):
    monkeypatch.setattr(fb,'fetch_capture',lambda url:response(html(**change)))
    observed=fb.fetch_html(URL)
    assert 'provenance_verified' not in observed
    assert 'publication_verified' not in observed


def test_truncated_or_off_origin_redirect_is_not_verified(monkeypatch):
    monkeypatch.setattr(fb,'fetch_capture',lambda url:response(truncated=True))
    assert 'provenance_verified' not in fb.fetch_html(URL)
    monkeypatch.setattr(fb,'fetch_capture',lambda url:response(final_url="https://example.net/news/verified-a"))
    assert 'provenance_verified' not in fb.fetch_html(URL)


def test_body_charset_drift_cannot_import_another_body_proof(monkeypatch):
    source=response()
    source['html']=source['html'].replace(BODY,'Contradictory shortened article.')
    monkeypatch.setattr(fb,'fetch_capture',lambda url:source)
    assert 'provenance_verified' not in fb.fetch_html(URL)


def test_old_unbound_records_remain_unverified_without_reaccess(tmp_path):
    snapshot=acquire_document(URL,'f1',{},tmp_path,lambda url:{
        'html':html(),'content_type':'text/html','status':200
    })
    assert 'provenance_verified' not in snapshot['metadata']
    assert 'publication_verified' not in snapshot['metadata']
