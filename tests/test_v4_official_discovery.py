"""Synthetic adapter/gate tests; never independent or forecast performance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from bct.objective_lock import stamp_export
from bct.v4 import official_discovery as a, official_sources as f
from bct.v4.store import Ledger, sha, file_sha


def native(text='Supply of fifteen Zephyra Q73 cryogenic sampling modules, including fittings.'):
    return {'releases': [{'ocid': 'unseen-ocid', 'id': 'notice1', 'date': '2026-10-14T12:00:00Z',
        'tag': ['award', 'contract'], 'buyer': {'id': 'GB-buyer', 'name': 'Synthetic purchaser'},
        'tender': {'description': text, 'title': 'New instruments', 'lots': [{'id': 'lot1', 'status': 'complete'}]},
        'awards': [{'id': 'award1', 'mainProcurementCategory': 'goods', 'status': 'active', 'relatedLots': ['lot1'],
                    'suppliers': [{'id': 'maker-id', 'name': 'Synthetic supplier'}],
                    'items': [{'id': 'item1', 'deliveryAddresses': [{'region': 'DE'}]}]}],
        'contracts': [{'id': 'contract1', 'awardID': 'award1', 'status': 'active', 'dateSigned': '2026-10-13',
                      'period': {'endDate': '2029-12-31'}, 'value': {'amount': 800000000, 'currency': 'USD'}}]}]}


def extract(data):
    return a.extract_ocds(data, {'source_id': 'find_tender', 'url': 'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages/unseen-ocid',
                                'sha256': sha(json.dumps(data).encode()), 'acquired_at': '2026-10-16T08:00:00Z'})


def test_unseen_product_without_target_or_legacy_event_discovery():
    d = native(); r = extract(d); e, = r['events']
    assert e['product'] == 'Zephyra Q73 cryogenic sampling modules' and e['quantity'] == '15'
    assert e['state'] == 'SOURCE_BOUND_EVENT' and e['target']['region']['normalized'] == 'DE'
    assert e['customer_need_date'] is None and e['period'] is None  # not contract end
    assert e['target']['supply_pool'] is None and not e['qualified']
    assert f.recheck(r['facts'][0], d) > 8
    assert not any(b['product'] == e['product'] for b in r['baseline'])


@pytest.mark.parametrize('text', ['Provision of legal services.', 'Supply of software licences.',
    'Purchase of 800000000 USD securities.', 'Provision of a case management system.',
    'Supply of equipment.', 'Purchase of Xena turbines and Ralo pumps.'])
def test_nonphysical_generic_or_mixed_objects_never_adopted(text):
    assert not extract(native(text))['events']


def test_ordered_equipment_not_its_future_output_or_money():
    e, = extract(native('Supply of two Zephyra Q73 sampling modules for producing wafers. The contract value is $800 million.'))['events']
    assert e['product'] == 'Zephyra Q73 sampling modules' and e['quantity'] == '2'
    assert 'wafers' not in e['product'] and e['qualified_capacity'] is None


@pytest.mark.parametrize('change,reason', [('cancel', 'PARENT_LOT_CONFLICT'), ('unsigned', 'NO_SIGNED_CONTRACT'),
                                        ('plan', 'PLANNED_NOT_CONFIRMED_PURCHASE'), ('negation', 'NEGATED_PURCHASE')])
def test_conflicts_and_plans_preserve_proposals_without_adoption(change, reason):
    d = native()
    if change == 'cancel': d['releases'][0]['tender']['lots'][0]['status'] = 'cancelled'
    if change == 'unsigned': del d['releases'][0]['contracts'][0]['dateSigned']
    if change == 'plan': d['releases'][0]['tender']['description'] += ' The buyer plans to purchase after approval.'
    if change == 'negation': d['releases'][0]['tender']['description'] += ' The buyer did not order this product.'
    e, = extract(d)['events']; assert reason in e['blockers'] and e['state'] == 'DISCOVERY_PROPOSAL'


def test_multiple_identified_items_and_release_versions_have_separate_locations():
    d = native(); award = d['releases'][0]['awards'][0]
    award['items'] = [{'id': 'a', 'description': 'Supply of two Xena Q7 modules.'},
                      {'id': 'b', 'description': 'Supply of three Ralo R9 probes.'}]
    old = deepcopy(d['releases'][0]); old['id'] = 'older'; old['date'] = '2026-10-12T12:00:00Z'; d['releases'].append(old)
    r = extract(d)
    assert len(r['events']) == 4 and len({x['document_id'] for x in r['documents']}) == 4
    assert {e['product'] for e in r['events']} == {'Xena Q7 modules', 'Ralo R9 probes'}
    assert all(f.recheck(row, d) for row in r['facts'])


def test_repeated_unitemized_phrases_not_first_match():
    assert not a.located_object('Supply of two Xena Q7 probes. Supply of two Xena Q7 probes.')


@pytest.mark.parametrize('product,context,level', [
    ('calibration', 'Provision of calibration, maintenance and repair services.', 'UNVERIFIED'),
    ('enterprise platform', 'Provision of an enterprise platform including software licensing and cloud services.', 'UNVERIFIED'),
    ('Machinery', 'Provision of machinery for industrial use.', 'PRODUCT_FAMILY'),
    ('maintenance equipment', 'Purchase of maintenance equipment.', 'PRODUCT_FAMILY'),
    ('Xena Q7 radio platforms', 'Supply of radio hardware and software upgrades.', 'LOCATED_CONTRACT_OBJECT')])
def test_source_bound_text_and_native_goods_code_not_semantic_confirmation(product, context, level):
    assert a.semantic_object(product, context)[0] == level


def test_missing_contract_id_isolated_without_inventing_id_or_stopping_batch():
    d = native(); bad = deepcopy(d['releases'][0]['contracts'][0]); del bad['id']
    d['releases'][0]['contracts'].insert(0, bad)
    r = extract(d)
    assert len(r['events']) == 1 and any(x['reason'] == 'CONTRACT_ID_ABSENT_NOT_INVENTED' for x in r['failures'])


def test_republished_ocds_identity_is_not_an_independent_event():
    d = native(); one = extract(d)['events'][0]
    two = a.extract_ocds(d, {'source_id': 'contracts_finder', 'url': 'https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search',
        'sha256': sha(json.dumps(d).encode()), 'acquired_at': '2026-10-16T08:00:00Z'})['events'][0]
    assert one['logical_id'] == two['logical_id'] and one['lineage'] == two['lineage']


def test_daily_increment_preserves_original_job_and_recovers_pending_day(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
    from v4_official_sources import next_daily_windows
    reg = {'global_sources': {'collection_jobs': [{'id': 'original', 'source_id': 'find_tender',
           'url': 'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?updatedFrom=2026-10-14T00%3A00%3A00&updatedTo=2026-10-14T23%3A59%3A59&limit=100',
           'format': 'JSON', 'max_pages': 1, 'archive_facts': True}]}}
    original = deepcopy(reg); new, = next_daily_windows(reg, through='2026-10-15')
    assert reg['global_sources']['collection_jobs'][0] == original['global_sources']['collection_jobs'][0]
    assert not next_daily_windows(reg, through='2026-10-15')
    l = Ledger(tmp_path/'ledger')
    with l.db: l.event('QUANTITATIVE_VALIDATION', {'reason': 'synthetic', 'policy': {'job_id': new['id'], 'source_id': 'find_tender', 'page': 1}})
    recovered = deepcopy(original); next_daily_windows(recovered, through='2026-10-16', ledger=l)
    assert {j['id'] for j in recovered['global_sources']['collection_jobs']} == {'original', 'official-daily-find_tender-2026-10-15', 'official-daily-find_tender-2026-10-16'}
    l.close()


def test_batch_page_cap_is_not_lifetime_cap_and_completed_pages_not_refetched(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
    from v4_official_sources import collect
    from urllib.parse import urlencode
    root = tmp_path/'captures'; root.mkdir()
    url = 'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?'+urlencode({'updatedFrom': '2026-10-14T00:00:00', 'limit': '100'})
    second = url+'&cursor=page2'
    for i, u in enumerate([url, second]):
        data = native(); data['releases'][0]['id'] = 'notice'+str(i)
        if i == 0: data['links'] = {'next': second}
        raw = json.dumps(data).encode(); p = root/(sha(u.encode())+'.json')
        p.write_text(json.dumps({'url': u, 'status': 200, 'raw_sha256': sha(raw), 'acquired_at': '2026-10-16T08:00:00Z'})); p.with_suffix('.raw').write_bytes(raw)
    reg = stamp_export({'global_sources': {'collection_jobs': [{'id': 'same-job', 'source_id': 'find_tender',
          'url': url, 'format': 'JSON', 'max_pages': 1, 'archive_facts': True, 'semantic_limits': 'synthetic'}]}})
    l = Ledger(tmp_path/'ledger'); first = collect(l, reg, tmp_path)
    assert any(p['status'] == 'BATCH_LIMIT_PENDING' and p['page'] == 2 for p in first['pages'])
    again = collect(l, reg, tmp_path)
    assert any(p['status'] == 'FACTS_STORED' and p['page'] == 2 for p in again['pages'])
    assert again['HTTP_requests_this_batch'] == 0
    assert collect(l, reg, tmp_path)['HTTP_requests_this_batch'] == 0
    l.close()


def test_indicative_stock_not_firm_date_or_allocable_capacity():
    raw = b'<h1>UnknownMaker ZZ9 modules</h1><p>In stock - Lead time 4 weeks - Contact us</p>'
    fact, e = a.indicative_supply(raw, {'source_id': 'issuer_amarisoft', 'url': 'https://amarisoft.com/synthetic',
                                       'sha256': sha(raw), 'acquired_at': '2026-10-16T08:00:00Z'})
    assert f.recheck(fact, raw.decode()) == 3
    assert e['quantity'] is e['supply_ready_date'] is None and e['published_at'] == 'UNKNOWN'
    assert e['state'] == 'SOURCE_BOUND_INDICATIVE_SUPPLY' and not e['qualified']


def test_actual_store_restart_dedup_and_source_tamper_block(tmp_path):
    r = extract(native()); p = stamp_export({'format': a.VERSION, 'plan_id': 'BCT-V4-Q-1.0', 'events': r['events'],
         'Q3': a.q3_input(r['events'], r['facts'], as_of='2026-10-16T10:00:00Z', documents=r['documents'])})
    l = Ledger(tmp_path/'ledger'); f.save(l, r['facts']); assert a.save(l, p)['added'] == 1; l.close()
    before = file_sha(tmp_path/'ledger/v4.sqlite3')
    l = Ledger(tmp_path/'ledger'); assert a.save(l, p)['added'] == 0; l.close()
    assert file_sha(tmp_path/'ledger/v4.sqlite3') == before
    bad = deepcopy(p); bad['events'][0]['quantity'] = '800000000'
    l = Ledger(tmp_path/'ledger')
    with pytest.raises(ValueError, match='EVENT_ID|QUANTITY'): a.save(l, bad)
    l.close()
    assert p['Q3']['eligible_pairs'] == p['Q3']['strict_engine_candidates'] == 0


def test_supplier_base_url_reuse_and_no_duplicate_or_failed_request(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
    from v4_official_discovery import supplier_discovery
    root = tmp_path/'cache'; root.mkdir(); url = 'https://amarisoft.com/product'
    raw = b'<base href="/"><h1>OtherModel K9</h1><a href="product">OtherModel K9</a>'
    p = root/(sha(url.encode())+'.json'); p.write_text(json.dumps({'url': url, 'status': 200, 'raw_sha256': sha(raw), 'acquired_at': '2026-10-16T08:00:00Z'})); p.with_suffix('.raw').write_bytes(raw)
    e = {'id': 'event', 'logical_id': 'logical', 'state': 'SOURCE_BOUND_EVENT', 'product': 'OtherModel K9'}
    result = supplier_discovery({'events': [e], 'supplier_sites': [{'event_id': 'event', 'supplier_id': 'maker', 'reported_site': url}]}, tmp_path/'run', [root])
    assert result['requests_charged_this_round'] == 0
    assert result['suppliers'][0]['visited'] == [url] and not result['suppliers'][0]['pending_urls']
