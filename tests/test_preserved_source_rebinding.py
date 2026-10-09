from copy import deepcopy
import json

import pytest

from bct import precursor_collection as collection
from bct.target_acquisition import digest


def fixture():
    url='https://www.hpcwire.com/2026/10/05/source-rebinding-test/'
    article={'@type':'NewsArticle','@id':url+'#article','url':url,
             'publisher':{'name':'HPCwire'},'datePublished':'2026-10-05T12:00:00+00:00'}
    raw=('''<html><head><link rel="canonical" href="'''+url+'''">
    <meta property="og:site_name" content="HPCwire"><script type="application/ld+json">'''
    +json.dumps(article)+'''</script></head><body class="wp-theme-hpc-theme single-post">
    <div class="article-card-wrapper normal-mode"><div class="w-100">
    <p>The approved supply line will be ready in 2028.</p><p>Demand starts in 2027.</p></div></div>
    <article class="article-card mb-30"><h2>Related article</h2><p>A different article stops...</p></article>
    </body></html>''').encode()
    current=collection.official_source.verify(raw,url,url,'2026-10-06T00:00:00+00:00')
    assert current['provenance']=='PASS'
    old_body='Related article\nA different article stops...'
    old={**current,'document_id':'legacy','body':old_body,'body_sha256':digest(old_body),
         'version':digest(old_body),'scope_read_mode':'LIVE_FRESH','scope_reader_version':'old-reader'}
    return old,raw,current


def test_exact_preserved_card_can_derive_primary_version_without_mutating_old_snapshot():
    old,raw,current=fixture();before=deepcopy(old)
    view=collection.verified_stored_snapshot(old,raw)
    assert old==before and view['prior_source_snapshot']==before
    assert view['body_sha256']==current['body_sha256']!=old['body_sha256']
    assert view['version']==view['body_sha256'] and view['raw_sha256']==old['raw_sha256']
    assert view['acquired_at']==old['acquired_at'] and view['scope_read_mode']=='BACKFILL_QA'
    assert view['source_version_correction']['prior_completeness']=='PARTIAL'
    assert collection.verified_stored_snapshot(old,raw)==view


@pytest.mark.parametrize('mutation',['metadata','body','html','hash','preview','hidden'])
def test_rebinding_does_not_accept_unverified_or_unrelated_changes(mutation):
    old,raw,current=fixture()
    if mutation=='metadata':old['published_at']='2026-10-04T12:00:00+00:00'
    elif mutation=='body':
        old['body']='A fabricated related article...';old['body_sha256']=old['version']=digest(old['body'])
    elif mutation=='html':raw=raw.replace(b'approved supply',b'unverified supply')
    elif mutation=='hash':old['version']='wrong'
    elif mutation=='preview':
        raw=raw.replace(b'normal-mode',b'normal-mode teaser');old['raw_sha256']=digest(raw)
    else:
        raw=raw.replace(b'class="w-100"',b'class="w-100" hidden');old['raw_sha256']=digest(raw)
    with pytest.raises(ValueError):collection.verified_stored_snapshot(old,raw)


def test_unchanged_primary_body_keeps_its_original_version_and_reading_mode():
    old,raw,current=fixture();current.update(document_id='primary',scope_read_mode='LIVE_FRESH')
    assert collection.verified_stored_snapshot(current,raw)==current
