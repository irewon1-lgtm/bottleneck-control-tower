import json
from pathlib import Path
import pytest
from bct import shadow_sources_v2 as s


def test_atom_keeps_publication_separate_from_updated():
    raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>A</id><title>8-K</title><updated>2026-10-05</updated><link href="https://www.sec.gov/Archives/edgar/data/1/a-index.html"/></entry></feed>'
    lead=s.feed_links(raw,'https://www.sec.gov/','sec_atom',1)[0]
    assert lead['recorded_publication'] is None
    assert lead['recorded_updated']=='2026-10-05'


def test_index_rejects_unapproved_hosts_and_duplicates():
    source={'kind':'official_index','limit':3,'article_hosts':['issuer.example'],'article_path_pattern':'/news/'}
    raw=b'<a href="https://other.example/news/a">other</a><a href="/news/a">a</a><a href="/news/a">repeat</a>'
    assert s.discover(source,raw,'https://issuer.example')==[{'url':'https://issuer.example/news/a','title':'a','recorded_publication':None}]


def test_live_root_rejected_before_fetch(tmp_path,monkeypatch):
    root=tmp_path/'live-state'/'store'
    monkeypatch.setattr(s,'fetch',lambda *a:pytest.fail('network must not execute'))
    with pytest.raises(ValueError,match='LIVE_STORE_FORBIDDEN'):s.intake({'sources':[]},root)


def test_sec_contact_is_required_without_inventing_email(monkeypatch):
    monkeypatch.delenv('BCT_SEC_USER_AGENT',raising=False)
    with pytest.raises(ValueError,match='SEC_OPERATOR_CONTACT_NOT_CONFIGURED'):
        s._get('https://www.sec.gov/Archives/edgar/data/1/a.htm',{'kind':'sec_atom'})


def test_index_failure_does_not_stop_next_source(tmp_path,monkeypatch):
    calls=[]
    def get(url,source):
        calls.append(url)
        if 'blocked' in url:raise ValueError('denied')
        return b'<rss><channel/></rss>',url,200,'application/rss+xml'
    monkeypatch.setattr(s,'_get',get)
    sources=[{'id':x,'kind':'official_feed','url':'https://'+x+'.example','article_hosts':[x+'.example']} for x in ('blocked','okay')]
    docs,receipts=s.intake({'sources':sources},tmp_path/'output')
    assert len(calls)==2 and not docs and receipts[1]['status']=='INDEX_RECEIVED'
    assert receipts[1]['blocker']=='SOURCE_INDEX_NO_ELIGIBLE_LINKS'


def test_award_summaries_never_become_verified_originals(tmp_path,monkeypatch):
    payload=json.dumps({'spending_level':'awards','results':[{'generated_internal_id':'CONT_X',
        'Award ID':'A-1','Recipient Name':'Issuer','Award Amount':1200000,
        'Awarding Agency':'Agency','Last Modified Date':'2026-10-01'}]}).encode()
    monkeypatch.setattr(s.USAspendingTransport,'post',lambda self,body:payload)
    detail=json.dumps({'generated_unique_award_id':'CONT_X','piid':'A-1','description':'Manufacturing contract',
                       'date_signed':'2025-01-01','period_of_performance':{'start_date':'2025-01-01','end_date':'2031-01-01','last_modified_date':'2026-10-01'}}).encode()
    monkeypatch.setattr(s,'_get',lambda url,source:(detail,url,200,'application/json'))
    docs,receipts=s.intake({'sources':[{'id':'awards','kind':'usaspending','query':'manufacturing','limit':1}]},tmp_path/'output')
    assert not docs
    assert receipts[0]['awards'][0]['last_modified_date']=='2026-10-01'
    doc=json.loads((tmp_path/'output/intake.json').read_text())['documents'][0]
    assert doc['published_at'] is None and doc['publisher'] is None
    assert doc['provenance']=='FAIL' and 'original_publication' in doc['provenance_blockers']
    assert json.loads(doc['body'])['period_of_performance']['end_date']=='2031-01-01'


def eia_html(url,date='October 1, 2026',closing=True):
    return (f'<html><head><meta name="agency" content="EIA - Energy Information Administration">'
            f'<meta property="og:title" content="Propane exports - U.S. Energy Information Administration (EIA)">'
            f'<meta property="og:url" content="{url}"><meta name="url" content="{url}">'
            '<meta property="og:type" content="article"></head><body><div class="tie-article">'
            f'<span class="date">{date}</span><h1>Propane exports</h1>'
            '<p>Data source: U.S. Energy Information Administration.</p>'
            '<p>Capacity will expand in 2031.</p>'+('</div></body></html>' if closing else '')).encode()


def test_eia_source_bound_date_identity_and_raw_locations():
    url='https://www.eia.gov/todayinenergy/detail.php?id=123'
    raw=eia_html(url)
    d=s.verify_page(raw,url,url,'2026-10-05T12:00:00+00:00',200,'text/html','eia')
    assert d['provenance']=='PASS' and d['published_at']=='2026-10-01'
    assert d['canonical_url'] is None and d['source_bound_url']==url
    assert d['body_sha256']==d['version']==s.v2.digest(d['body'].encode())
    for ref in d['source_proof']['article_sections']+d['source_proof']['metadata_references']:
        a,b=ref['locator']['start'],ref['locator']['end']
        assert ref['quote']==raw.decode()[a:b] and b>a
    s.v2.validate_document(d,'2026-10-05T12:00:00+00:00')


@pytest.mark.parametrize('change',['date_missing','body_unclosed','different_url','unknown_publisher'])
def test_eia_missing_proof_is_not_filled_by_source_domain(change):
    url='https://www.eia.gov/todayinenergy/detail.php?id=123'
    raw=eia_html(url,date='' if change=='date_missing' else 'October 1, 2026',closing=change!='body_unclosed')
    if change=='unknown_publisher':raw=raw.replace(b'EIA - Energy Information Administration',b'')
    final=url+'&other=1' if change=='different_url' else url
    d=s.verify_page(raw,url,final,'2026-10-05T12:00:00+00:00',200,'text/html','eia')
    assert not d['provenance_verified'] and d['provenance']=='FAIL'


def test_eaton_metadata_date_must_match_visible_release_date():
    url='https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/line.html'
    raw=(f'<html><head><link rel="canonical" href="{url}"><meta name="page-url" content="{url}">'
         f'<meta property="og:url" content="{url}"><meta property="og:site_name" content="Eaton">'
         '<meta name="publish-date" content="August 17, 2026"></head><body><h1 class="eaton-title__headline">Line expansion</h1>'
         '<div class="eaton-text-default__content"><p>August 17, 2026</p><p>New line in 2031.</p></div>'
         '<div class="eaton-text-default__content"><p>About Eaton</p></div></body></html>').encode()
    d=s.verify_page(raw,url,url,'2026-10-05T12:00:00+00:00',200,'text/html','eaton')
    assert d['provenance']=='PASS' and d['published_at']=='2026-08-17' and d['publisher']=='Eaton'
    bad=raw.replace(b'<p>August 17, 2026</p>',b'<p>August 18, 2026</p>')
    assert not s.verify_page(bad,url,url,'2026-10-05T12:00:00+00:00',200,'text/html','eaton')['provenance_verified']


def test_eaton_official_sitemap_not_lastmod_as_publication(tmp_path,monkeypatch):
    source={'article_hosts':['www.eaton.com'],'article_path_pattern':'/news-releases/20[0-9]{2}/','limit':2}
    index=b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://www.eaton.com/us/en-us.sitemap.xml</loc></sitemap></sitemapindex>'
    urls=b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/line.html</loc><lastmod>2026-10-01</lastmod></url><url><loc>https://wrong.example/news-releases/2026/line.html</loc></url></urlset>'
    monkeypatch.setattr(s,'_get',lambda url,source:(index if url.endswith('/sitemap.xml') else urls,url,200,'application/xml'))
    leads=s.eaton_sitemap(source,tmp_path)
    assert len(leads)==1 and leads[0]['recorded_updated']=='2026-10-01' and leads[0]['recorded_publication'] is None


def test_eaton_byline_template_has_independent_publication_and_publisher_proof():
    url='https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/supplier.html'
    raw=(f'<html><head><link rel="canonical" href="{url}"><meta name="page-url" content="{url}">'
         f'<meta property="og:url" content="{url}"><meta property="og:site_name" content="Eaton">'
         '<meta name="publish-date" content="January 6, 2026"></head><body>'
         '<h1 class="eaton-title__eyebrow-and-byline">Suppliers</h1>'
         '<div class="eaton-title__byline">Eaton, 01/06/2026</div>'
         '<div class="eaton-text-default__content"><p>Supply chain recognition.</p></div>'
         '<div class="eaton-text-default__content">Eaton is an intelligent power management company.</div></body></html>').encode()
    assert s.verify_page(raw,url,url,'2026-10-05T12:00:00+00:00',200,'text/html','eaton')['provenance']=='PASS'
    wrong=raw.replace(b'Eaton, 01/06/2026',b'Eaton, 06/01/2026')
    assert not s.verify_page(wrong,url,url,'2026-10-05T12:00:00+00:00',200,'text/html','eaton')['provenance_verified']


def test_failed_inputs_share_common_output_schema():
    d=s.common_document({'origin_url':'https://www.sec.gov/','error':'SEC_OPERATOR_CONTACT_NOT_CONFIGURED'})
    assert d['provenance']=='BLOCKED' and d['publisher'] is None
    assert all(k in d for k in ('origin_id','origin_url','publisher','published_at','acquired_at','body','body_sha256','version','provenance_evidence'))


def test_sec_link_resolution_alone_is_not_provenance(tmp_path,monkeypatch):
    index='https://www.sec.gov/Archives/edgar/data/1/a-index.html'
    primary='https://www.sec.gov/Archives/edgar/data/1/a.htm'
    feed=f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><link href="{index}"/></entry></feed>'.encode()
    html=f'<html><head><link rel="canonical" href="{primary}"><meta property="og:site_name" content="Issuer"><meta property="article:published_time" content="2025-01-01T00:00:00Z"></head><body><article>Issuer orders model AX-1 production in 2031.</article></body></html>'.encode()
    def get(url,source):
        raw=feed if '/feed' in url else f'<a href="{primary}">8-K</a>'.encode() if url==index else html
        return raw,url,200,'text/html'
    monkeypatch.setattr(s,'_get',get)
    docs,_=s.intake({'sources':[{'id':'sec','kind':'sec_atom','url':'https://www.sec.gov/feed','article_hosts':['www.sec.gov']}]},tmp_path/'output')
    assert not docs
    document=json.loads((tmp_path/'output/intake.json').read_text())['documents'][0]
    assert 'SEC_ISSUER_ACCEPTANCE_PRIMARY_DOCUMENT_BINDING_UNVERIFIED' in document['error']


def test_sec_primary_form_requires_issuer_acceptance_and_body_binding(tmp_path,monkeypatch):
    index='https://www.sec.gov/Archives/edgar/data/1/0001/a-index.html'
    primary='https://www.sec.gov/Archives/edgar/data/1/0001/a.htm'
    html=b'''<html><span class="companyName">Aster Corporation</span><div>Accepted</div><div>2025-01-01 10:00:00</div>
    <table><tr><td>1</td><td><a href="a.htm">primary</a></td><td>8-K</td></tr></table></html>'''
    monkeypatch.setattr(s,'_get',lambda url,source:(html,url,200,'text/html'))
    lead=s._sec_primary({'kind':'sec_atom'},{'url':index},tmp_path)
    assert lead['url']==primary and lead['issuer_cik']=='1'
    body=b'<html><body>FORM 8-K\nAster Corporation\nOrders for model AX-1 manufacturing in 2031.</body></html>'
    d=s.verify_sec(body,lead,primary,'2026-10-05T12:00:00+00:00',200,'text/html')
    assert d['provenance_verified'] and d['origin_publisher']=='Aster Corporation'
    assert d['published_at']=='2025-01-01T10:00:00-05:00'
    s.v2.validate_document(d,'2026-10-05T12:00:00+00:00')
    assert not s.verify_sec(body.replace(b'Aster Corporation',b'Other Issuer'),lead,primary,'2026-10-05T12:00:00+00:00',200,'text/html')['provenance_verified']
    assert not s.verify_sec(body,lead,primary+'?other','2026-10-05T12:00:00+00:00',200,'text/html')['provenance_verified']


def test_completed_document_not_downloaded_and_unverified_body_not_pass(tmp_path,monkeypatch):
    feed=b'<rss><channel><item><link>https://issuer.example/news/old</link></item><item><link>https://issuer.example/news/new</link></item></channel></rss>'
    calls=[]
    def get(url,source):
        calls.append(url)
        return (feed if url.endswith('/feed') else b'<html><main><p>Unknown production capacity.</p></main></html>'),url,200,'text/html'
    monkeypatch.setattr(s,'_get',get)
    source={'id':'issuer','kind':'official_feed','url':'https://issuer.example/feed','article_hosts':['issuer.example']}
    docs,receipts=s.intake({'sources':[source]},tmp_path/'output',completed_urls=['https://issuer.example/news/old'])
    assert 'https://issuer.example/news/old' not in calls and not docs
    saved=json.loads((tmp_path/'output/intake.json').read_text())
    assert saved['documents'][0]['provenance_verified'] is False


def test_provenance_verified_primary_html_can_reach_shadow_input(tmp_path,monkeypatch):
    url='https://issuer.example/news/a'
    html=f'<html><head><link rel="canonical" href="{url}"><meta property="og:site_name" content="Issuer"><meta property="article:published_time" content="2025-01-01T00:00:00Z"></head><body><article><p>Issuer orders manufacturer Aster model AX-1 production for delivery in 2031.</p></article></body></html>'.encode()
    feed=f'<rss><channel><item><link>{url}</link></item></channel></rss>'.encode()
    monkeypatch.setattr(s,'_get',lambda u,source:(feed if u.endswith('/feed') else html,u,200,'text/html'))
    source={'id':'issuer','kind':'official_feed','url':'https://issuer.example/feed','article_hosts':['issuer.example']}
    docs,_=s.intake({'sources':[source]},tmp_path/'output')
    assert len(docs)==1 and docs[0]['provenance_verified']
    result=s.shadow_run(tmp_path/'shadow',docs)
    assert result['counts']['documents_valid']==1 and result['freeze']['live_early']==0
