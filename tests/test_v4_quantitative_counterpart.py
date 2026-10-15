"""Counterpart discovery guards; synthetic functionality, NOT AI accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from bct.v4 import quantitative_counterpart as q
from bct.v4.store import Ledger, sha, file_sha


def seed(product='Model-Q equipment', role='DEMAND'):
    return {'id': 'seed', 'product': product, 'role': role,
            'source': {'document_id': 'first', 'body_sha256': 'first-hash'}, 'fields': {}}


def doc(text, **changes):
    d = {'document_id': 'second', 'body': text, 'body_sha256': sha(text.encode()),
         'raw_sha256': sha(b'native'), 'origin_url': 'https://www.airbus.com/example',
         'origin_publisher': 'Airbus', 'provenance': 'PASS', 'body_status': 'FULL',
         'published_at': '2026-10-01', 'acquired_at': '2026-10-15'}
    d.update(changes); return d


def test_opposite_role_context_exact_repeated_word_positions_no_promotion():
    text = 'Model-Q equipment brochure\nHowever qualification is not complete.\nModel-Q equipment production is planned for 2028.\nCapacity is not available today.'
    d = doc(text); r = q.discover(seed(), [d], as_of='2026-10-15')
    assert r['requested_role'] == 'SUPPLY' and len(r['selected_sources']) == 1
    for c in r['selected_sources'][0]['contexts']:
        assert text[c['product_start']:c['product_end']] in q.search_terms(seed()['product'])
        assert sha(text[c['start']:c['end']].encode()) == c['context_sha256']
    assert r['s_stage'] == 'UNKNOWN' and r['selected_sources'][0]['adoption'] == 'REVIEW_PENDING'
    assert r['selected_sources'][0]['independence'] == 'UNKNOWN'


def test_constraint_searches_customers_and_irrelevant_product_does_not_match():
    r = q.discover(seed(role='CONSTRAINT'), [doc('Customer ordered Model-Q equipment.')], as_of='2026-10-15')
    assert r['requested_role'] == 'DEMAND' and len(r['selected_sources']) == 1
    r = q.discover(seed(), [doc('Model-R equipment production capacity doubled.')], as_of='2026-10-15')
    assert not r['selected_sources']


@pytest.mark.parametrize('changes,reason', [({'provenance': 'BLOCKED'}, 'SOURCE_OR_FULLNESS_UNVERIFIED'),
    ({'published_at': '2027-01-01'}, 'FUTURE_PUBLICATION'), ({'published_at': None}, 'PUBLICATION_UNKNOWN'),
    ({'body_sha256': 'wrong'}, 'SOURCE_HASH_MISMATCH'),
    ({'origin_url': 'https://example.com/news'}, 'PRIMARY_SOURCE_UNVERIFIED')])
def test_source_gates_stay_closed(changes, reason):
    r = q.discover(seed(), [doc('Model-Q equipment capacity expanded.', **changes)], as_of='2026-10-15')
    assert not r['selected_sources'] and r['rejected_sources'][0]['reason'] == reason


def test_real_regression_cases_preserve_order_quantity_and_expected_shipment_not_need():
    packet = json.loads(Path('docs/v4/quantitative/product-facts.json').read_text())
    records = q.seeds(packet['records'], [])
    h = next(r for r in records if r['product'] == 'H225M')
    a = next(r for r in records if r['product'] == 'A321neo')
    f = next(r for r in records if 'FOX-XP' in r['product'])
    assert h['fields']['quantity'] == '12' and a['fields']['quantity'] == '2'
    assert h['role'] == a['role'] == 'DEMAND'
    assert f['role'] == 'SUPPLY_PLAN' and not f['fields']['need_window'] and not f['fields']['qualified_capacity']
    assert f['planned_delivery'] == 'first half of calendar 2027'


def test_bounded_sources_version_dedup_private_state_and_restart(tmp_path):
    d = doc('Model-Q equipment capacity is expanding.')
    docs = [{**d, 'document_id': str(i), 'body_sha256': d['body_sha256']} for i in range(9)]
    p = q.packet([seed()], docs, as_of='2026-10-15')
    assert len(p['records'][0]['selected_sources']) == 1
    l = Ledger(tmp_path); assert q.save(l, p)['added'] == 1; l.close()
    l = Ledger(tmp_path); before = file_sha(l.path); assert q.save(l, p)['added'] == 0
    assert file_sha(l.path) == before; l.close()
    bad = deepcopy(p); bad['records'][0]['s_stage'] = 'S3'
    l = Ledger(tmp_path)
    with pytest.raises(ValueError, match='PROMOTION'): q.save(l, bad)
    l.close()


def test_link_acquisition_no_failed_url_retry_and_other_host_continues(tmp_path):
    p = q.packet([seed()], [], as_of='2026-10-15'); r = p['records'][0]
    r['official_link_queue'] = [{'url': 'https://'+h+'/product', 'parent_document_id': 'first',
                                 'status': 'UNFETCHED_OFFICIAL_LINK_NOT_EVIDENCE'}
                                for h in ['www.airbus.com', 'www.aehr.com']]
    r['id'] = sha([q.VERSION, {k: v for k, v in r.items() if k != 'id'}])
    calls = []
    class Client:
        def fetch(self, url):
            calls.append(url)
            if 'airbus' in url: raise TimeoutError()
            return b'<html><title>Model-Q</title><p>Model-Q equipment capacity.</p></html>', url, 200, 'text/html'
    l = Ledger(tmp_path)
    first = q.acquire(p, l, Client()); assert len(first) == 2
    assert first[0]['status'] == 'FAILED_ISOLATED' and first[1]['status'] == 'CAPTURED'
    l.close(); l = Ledger(tmp_path)
    assert q.acquire(p, l, Client()) == [] and len(calls) == 2; l.close()


def test_same_target_capacity_without_need_or_qualification_never_counts_pair():
    r = q.discover(seed(), [doc('Model-Q equipment production capacity is 100 units per year.')], as_of='2026-10-15')
    assert {'need_window', 'qualified_capacity', 'customer'} <= set(r['missing_fields'])
    assert r['s_stage'] == 'UNKNOWN' and r['selected_sources'][0]['scope_equivalence'] == 'UNKNOWN'


def test_product_page_date_is_not_an_article_date_and_receipt_bound_article_is_preserved():
    raw=b'<script type="application/ld+json">{"@type":"WebPage","@id":"https://www.airbus.com/example","datePublished":"2026-10-01"}</script>'
    d=doc('Model-Q');q.bind_publication(d,raw)
    assert d['published_at'] is None and d['provenance']=='BLOCKED'
    raw=raw.replace(b'WebPage',b'NewsArticle');d=doc('Model-Q');q.bind_publication(d,raw)
    assert d['published_at']=='2026-10-01'and d['provenance']=='PASS'


def test_batch_budget_leaves_other_links_unattempted(tmp_path):
    p=q.packet([seed()],[],as_of='2026-10-15');r=p['records'][0]
    r['official_link_queue']=[{'url':'https://www.airbus.com/'+name,'parent_document_id':'first',
                              'status':'UNFETCHED_OFFICIAL_LINK_NOT_EVIDENCE'}for name in ['one','two']]
    r['id']=sha([q.VERSION,{k:v for k,v in r.items()if k!='id'}])
    class Client:
        def fetch(self,url):raise TimeoutError()
    l=Ledger(tmp_path)
    assert len(q.acquire(p,l,Client(),max_calls=1))==1
    assert l.db.execute("SELECT count(*) FROM events WHERE kind='Q2_COUNTERPART_FETCH_ATTEMPT'").fetchone()[0]==1
    l.close()
