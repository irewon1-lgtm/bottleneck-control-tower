"""Authored development counterexamples; not an independent accuracy cohort."""
from copy import deepcopy
import json
import pytest
from bct.v4.reading_quality import validate_packet, plan_pages, save_result, RUN_ID
from bct.v4.research_reading import generate, JSONAdapter, PROMPT
from bct.v4.store import Ledger, sha
from test_v4_free_ai import config, document


def packet(text, name, role='DEMAND_INCREASE', actuality='ACTUAL', **fields):
    return {'event': text, 'event_attributes': {'product': name, 'role': role, 'actuality': actuality, **fields}}


def read(body, *items):
    d = document(body)
    return validate_packet(json.dumps({'extractions': list(items)}), d,
                           [{'start': 0, 'end': len(body), 'text': body}])


@pytest.mark.parametrize('product', ['cryogenic valves', 'optical transceivers', 'cell culture vessels',
                                    'lithium cells', 'logistics cranes', 'radar modules'])
def test_new_products_ordered_object_across_industries(product):
    text = f'Atlas ordered two {product}.'
    r = read(text, packet(text, product))
    assert r['records'][0]['event_status'] == 'ADOPTED_RESEARCH_EVENT'
    assert r['records'][0]['role'] == 'DEMAND_INCREASE'
    assert r['records'][0]['s_stage'] == 'UNKNOWN'
    assert r['S1_S2_S3'] == [0, 0, 0]


def test_one_invalid_enum_or_item_never_drops_valid_other_product():
    t = 'Atlas ordered cryogenic valves. Lithium cells demand declined.'
    r = read(t, packet('Atlas ordered cryogenic valves.', 'cryogenic valves'),
             packet('Lithium cells demand declined.', 'Lithium cells', 'DEMAND_DECREASE'), {})
    assert len(r['records']) == 2
    assert r['records'][0]['event_status'] == 'ADOPTED_RESEARCH_EVENT'
    assert r['records'][1]['event_status'] == 'DISCOVERY_ONLY'
    assert {x['reason'] for x in r['held']} == {'UNSUPPORTED_ROLE_OR_ACTUALITY_EVENT_HELD_PRODUCT_ONLY', 'INVALID_EXTRACTION_ITEM'}


def test_invalid_fact_does_not_invent_value_or_erase_located_product():
    t = 'Atlas ordered four cryogenic valves.'
    x = packet(t, 'cryogenic valves', quantity='4', customer_group='unmentioned')
    r = read(t, x)
    assert len(r['records']) == 1 and not r['records'][0]['fields']
    assert len(r['held']) == 2 and r['records'][0]['original_model_item'] == x


def test_partial_plural_and_business_object_are_not_physical_identity():
    t = 'Atlas discussed advanced optical processors and production business for new devices.'
    r = read(t, packet(t, 'advanced optical processor', 'UNKNOWN'),
             packet(t, 'production business for new devices', 'UNKNOWN'))
    assert not r['records']
    assert {h['reason'] for h in r['held']} == {'PRODUCT_TOKEN_BOUNDARY', 'NON_PRODUCT_RELATIONAL_HEAD'}


def test_currency_prefix_is_not_a_generic_physical_count():
    t = 'Atlas ordered USD 800 million cryogenic valves.'
    r = read(t, packet(t, 'cryogenic valves', quantity='800 million', unit='valves'))
    assert 'quantity' not in r['records'][0]['fields']


def test_other_product_count_and_buyer_in_same_sentence_are_not_transferred():
    t = 'Atlas ordered three cryogenic valves and Beta ordered five optical transceivers.'
    r = read(t, packet(t, 'cryogenic valves', quantity='five', customer_group='Beta'))['records'][0]
    assert 'quantity' not in r['fields'] and 'customer_group' not in r['fields']
    assert r['event_status'] == 'ADOPTED_RESEARCH_EVENT'
    assert r['original_model_item']['event_attributes']['quantity'] == 'five'


def test_money_recipient_wrong_time_and_output_not_adopted_as_order_fields():
    t = 'Atlas received a $800 million grant for lithium cells in 2028.'
    r = read(t, packet(t, 'lithium cells', 'SUPPLY_INCREASE', quantity='800 million',
                       customer_group='Atlas', ready_time='2028'))
    x = r['records'][0]
    assert x['event_status'] == 'DISCOVERY_ONLY' and not x['fields']
    assert len(x['rejected_fields']) == 2  # monetary value held earlier by exact decoder
    t = 'Atlas ordered test equipment to produce lithium cells.'
    r = read(t, packet(t, 'lithium cells'))
    assert r['records'][0]['event_status'] == 'DISCOVERY_ONLY'


def test_literal_number_buyer_and_quantity_remain_source_bound():
    t = 'Atlas ordered four cryogenic valves.'
    r = read(t, packet(t, 'cryogenic valves', quantity='four', unit='valves', customer_group='Atlas'))
    x = r['records'][0]
    assert x['fields']['quantity']['surface'] == 'four'
    assert x['quantity_conversion']['normalized'] == '4'
    assert x['fields']['customer_group']['surface'] == 'Atlas'


@pytest.mark.parametrize('tail', ['However, this order was cancelled.', 'However, this order was not confirmed.'])
def test_exact_short_order_cannot_hide_later_counterevidence(tail):
    s = 'Atlas ordered cryogenic valves.'
    r = read(s+' '+tail, packet(s, 'cryogenic valves'))
    assert r['records'][0]['event_status'] == 'DISCOVERY_ONLY'


@pytest.mark.parametrize('name', ['Apex Corporation', 'privacy policy', 'production business', 'Hydrogen project'])
def test_nonproduct_structural_heads(name):
    t = f'Atlas announced {name}.'
    r = read(t, packet(t, name, 'UNKNOWN'))
    assert not r['records'] and r['held']


def test_supply_relief_plans_and_unrelated_product_are_separate():
    for t, name, role, adopted in [
        ('Cryogenic valves production decreased.', 'Cryogenic valves', 'SUPPLY_DECREASE', True),
        ('Optical transceivers lead times shortened.', 'Optical transceivers', 'RELIEF', True),
        ('Lithium cells production will increase.', 'Lithium cells', 'SUPPLY_INCREASE', False),
        ('Cryogenic valves are stable; lithium cells production decreased.', 'Cryogenic valves', 'SUPPLY_DECREASE', False),
    ]:
        r = read(t, packet(t, name, role))['records'][0]
        assert (r['event_status'] == 'ADOPTED_RESEARCH_EVENT') == adopted
        if 'will' in t: assert r['actuality'] == 'PLAN'


def test_duplicate_or_missing_quote_and_outside_transmitted_window_still_held():
    t = 'Atlas ordered cryogenic valves.'
    r = read(t+' '+t, packet(t, 'cryogenic valves'))
    assert not r['records']
    d = document(t+' Lithium cells production decreased.')
    r = validate_packet(json.dumps({'extractions': [packet('Lithium cells production decreased.', 'Lithium cells')]}),
                        d, [{'start': 0, 'end': len(t), 'text': t}])
    assert not r['records']
    with pytest.raises(ValueError, match='INVALID_JSON'):
        validate_packet('{"extractions":[],"extractions":[]}', d, [])


def test_pages_plan_full_context_and_keep_read_count_zero_until_response():
    text = '\n'.join(f'Plant {i} manufactures novel instruments and has detailed engineering specifications.' for i in range(8))
    d = document(text);c = config();c.update(max_input_characters=200,max_windows=2)
    p = plan_pages(d, c, {})
    assert len(p['pages']) > 1 and p['prepared']['read_characters'] > 200
    assert p['actually_read']['read_characters'] == 0
    assert p['prepared']['read_characters'] + p['prepared']['unread_characters'] == len(text)
    for page in p['pages']:
        assert page['selected_characters'] <= 200
        for w in page['windows']: assert text[w['start']:w['end']] == w['text']


def test_linked_cancellation_never_cut_to_fit_page():
    t = 'Atlas ordered cryogenic valves.\nHowever, this order was cancelled. '+('Unfinished conditions remain. '*12)
    d = document(t);c = config();c['max_input_characters'] = 100
    with pytest.raises(ValueError, match='NO_COMPLETE_SAFE'): plan_pages(d, c, {})


@pytest.mark.parametrize('change', ['provenance','publication','secret','restriction'])
def test_planner_never_releases_existing_source_or_transfer_holds(change):
    d = document('Atlas ordered cryogenic valves.')
    if change == 'provenance': d['provenance'] = 'BLOCKED'
    if change == 'publication': d['published_at'] = 'UNKNOWN'
    if change == 'restriction': d['api_transfer_forbidden'] = True
    if change == 'secret':
        d['body'] += ' password=private';d['body_sha256'] = sha(d['body'].encode())
    from bct.v4.free_ai import APIError
    with pytest.raises((ValueError, APIError)): plan_pages(d, config(), {})


def test_save_restart_backup_restore_preserves_raw_and_rejection_history(tmp_path):
    t = 'Atlas ordered four cryogenic valves.';d = document(t)
    text = json.dumps({'extractions': [packet(t, 'cryogenic valves', quantity='4')]})
    windows = [{'start': 0, 'end': len(t), 'text': t}]
    l = Ledger(tmp_path/'live');r = save_result(l, d, text, windows)
    n = l.status();l.backup(tmp_path/'restore/v4.sqlite3');l.close()
    for root in ('live','restore'):
        l = Ledger(tmp_path/root)
        assert save_result(l, d, text, windows) == r and l.status() == n
        assert r['original_response'] == text and r['held']
        l.close()


def test_fixed_task_cap_survives_new_router_without_http(tmp_path, monkeypatch):
    l = Ledger(tmp_path/'api');c = config();c['max_calls_per_run'] = 1
    with l.db:
        l.event('API_ATTEMPT', {'run_id': RUN_ID, 'reserved_tokens': 100, 'provider': 'groq', 'at': '2026-10-14T10:00:00+00:00', 'attempt_id': 'existing'})
    from bct.v4.free_ai import Router
    monkeypatch.setattr(Router, 'available', lambda *args: None)
    monkeypatch.setattr(JSONAdapter, 'call', lambda *args: pytest.fail('extra HTTP forbidden'))
    d = document('Atlas ordered valves.')
    r = generate(l, c, d['body'], d, [], phase='reading-quality', run_id=RUN_ID)
    assert r['status'] == 'WAIT_API' and r['reason'] == 'RUN_BUDGET'
    l.close()


def test_old_json_contract_default_is_unchanged():
    assert JSONAdapter({}).request('groq', {'prompt': 'source'}, 2048)[2]['messages'][0]['content'] == PROMPT


@pytest.mark.parametrize('status', [400, 401])
def test_json_mode_old_http_failure_does_not_move_to_new_contract(tmp_path, monkeypatch, status):
    l = Ledger(tmp_path/'api');d = document('Atlas ordered valves.')
    with l.db:
        l.event('API_ATTEMPT', {'document_id': d['document_id'], 'attempt_id': 'old', 'input_key': 'old-key'})
        l.event('API_ERROR', {'attempt_id': 'old', 'diagnostics': {'http_status': status}})
    monkeypatch.setattr(JSONAdapter, 'call', lambda *args: pytest.fail('old HTTP request retried'))
    r = generate(l, config(), d['body'], d, [], phase='reading-quality', system='Changed prompt', run_id=RUN_ID)
    assert r['status'] == 'BLOCKED_PREVIOUS_FAILED_DOCUMENT_NO_RETRY'
    l.close()
