"""Consumed development sources and authored grammar regressions; no holdout."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from bct import precursor_collection as collection, precursor_scope_reader as reader
from test_precursor_source_pipeline import doc


@pytest.fixture(scope='module')
def preserved_documents(tmp_path_factory):
    path = Path(__file__).resolve().parents[1] / 'docs/v4/reading-quality/research-snapshot.sqlite3.gz'
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == '49b3a551b4f68d6270aded7d1a9f1b3440bc34ea01159a234137c01f7c2b8b6a'
    restored = tmp_path_factory.mktemp('order-binding') / 'reading-quality.sqlite3'
    restored.write_bytes(gzip.decompress(payload))
    with sqlite3.connect(restored.as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
        documents = [json.loads(row[0]) for row in db.execute('select payload from documents')]
    for document in documents:
        assert hashlib.sha256(document['body'].encode()).hexdigest() == document['body_sha256']
    return {document['body_sha256']: document for document in documents}


@pytest.mark.parametrize('body_hash,start,end,name,offset', [
    ('46e75f874054d889f57961091c4add7f55f4da0831094cd498ae1115382f0557', 1024, 1133, 'FOX-XP', 1049),
    ('d8e72ad2ab877464236d72e31492b28ec44fce0152c2b734cb64d3f1443a09e9', 853, 1012, 'Sonoma', 894),
])
def test_actual_preserved_order_equipment_identity(preserved_documents, body_hash, start, end, name, offset):
    document = preserved_documents[body_hash]
    before = deepcopy(document)
    line = next(line for line in reader.sentences(document, reader.allowed_lines(document)[0])
                if (line['start'], line['end']) == (start, end))
    product = reader.bound_product(line, reader._products(document, line))
    assert product is not None and product['value'] == name
    assert product['locator'] == {'start': offset, 'end': offset + len(name)}
    assert product['reference']['source_quote'] == name
    assert document == before


def test_actual_order_list_parent_links_new_item_and_preserves_upgrade(preserved_documents):
    document = preserved_documents['46e75f874054d889f57961091c4add7f55f4da0831094cd498ae1115382f0557']
    structured = collection.structure(document)
    parent = next(event for event in structured['precursor_events'] if event['source_quote'] == 'The order includes:')
    product = parent['scope'].get('product')
    assert product and product['value'] == 'FOX-XP'
    assert product['link_kind'] == 'EXPLICIT_ORDER_LIST_ITEM'
    assert any('One new ultra-high-power' in ref['source_quote'] for ref in product['support_references'])
    assert not any('An upgrade' in ref['source_quote'] for ref in product['support_references'])
    assert parent['quantity'] == 'UNKNOWN' and parent['demand_status'] == 'UNKNOWN'
    assert not parent['qualified'] and not parent['coverage_complete'] and parent['window'] is None
    assert reader.validate_references(document, structured['retained_collection_events'])


@pytest.mark.parametrize('name', ['Horizon', 'Lumen', 'RX-ZZ'])
def test_generic_named_equipment_does_not_bind_its_customer_output(name):
    document = doc(f'The initial order includes multiple Forge {name}™ ultra-high-power package-level test and burn-in systems for production burn-in of silicon photonics chips and AI ASIC processors.')
    event = collection.structure(document)['precursor_events'][0]
    assert event['scope']['product']['value'] == name
    assert event['quantity'] == 'UNKNOWN' and event['window'] is None
    assert not event['qualified']


def test_two_new_order_list_products_remain_unresolved():
    structured = collection.structure(doc('The order includes:\nOne new Lumen™ wafer-level test and burn-in system, and\nOne new Horizon™ wafer-level test and burn-in system.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


def test_an_unresolved_list_item_cannot_disappear_from_parent_binding():
    structured = collection.structure(doc('The order includes:\nOne new Lumen™ burn-in system, and\nOne new Horizon™ burn-in system and an RX-ZZ burn-in system.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


def test_comma_coordinated_order_equipment_remains_unresolved():
    body = 'Signed new orders for Lumen™ burn-in systems, and Horizon™ burn-in systems.'
    document = doc(body)
    line = {'start': 0, 'end': len(body), 'quote': body}
    assert reader.bound_product(line, reader._products(document, line)) is None


@pytest.mark.parametrize('qualifier', ['subject to an option', 'cancelled', 'not ordered', 'planned', 'proposed'])
def test_qualified_list_item_does_not_become_parent_order_equipment(qualifier):
    structured = collection.structure(doc(f'The order includes:\nOne new Lumen™ burn-in system, {qualifier}.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


def test_existing_upgrade_is_not_a_new_order_list_item():
    structured = collection.structure(doc('The order includes:\nAn upgrade of an existing Lumen™ burn-in system to a higher power configuration.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


@pytest.mark.parametrize('body', [
    'The initial order includes multiple ASC 606 burn-in systems.',
    'The initial order includes ISO 9001 quality systems.',
    'The initial order includes FORM 10 accounting systems.',
    'Signed new orders for Lumen™ burn-in systems and Horizon™ burn-in systems.',
])
def test_codes_and_coordinated_equipment_are_not_one_model(body):
    document = doc(body)
    line = {'start': 0, 'end': len(body), 'quote': body}
    product = reader.bound_product(line, reader._products(document, line))
    assert product is None or product['value'] not in ('ASC', 'ASC 606', 'ISO', 'ISO 9001', 'FORM', 'FORM 10', 'Lumen', 'Horizon')


@pytest.mark.parametrize('word', ['Existing', 'Industrial', 'Qualified', 'Production', 'High-power'])
def test_capitalized_equipment_description_is_not_a_new_plain_model(word):
    body = f'{word} burn-in systems are used for testing.'
    document = doc(body)
    line = {'start': 0, 'end': len(body), 'quote': body}
    assert not any(product['value'] == word and product.get('identity_kind') == 'NAMED_ENGINEERING_EQUIPMENT'
                   for product in reader._products(document, line))


def test_serial_equipment_objects_remain_unresolved():
    body = 'The order includes Lumen™ burn-in systems, Horizon™ burn-in systems, and RX-ZZ burn-in systems.'
    document = doc(body)
    line = {'start': 0, 'end': len(body), 'quote': body}
    assert reader.bound_product(line, reader._products(document, line)) is None


def test_unrecognized_second_list_item_cannot_leave_the_first_selected():
    structured = collection.structure(doc('The order includes:\nOne new Lumen™ burn-in system, and\nFour new Horizon™ burn-in systems.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


@pytest.mark.parametrize('continuation', ['Two more new', 'A second new', 'One refurbished'])
def test_unknown_explicit_list_continuation_preserves_ambiguity(continuation):
    structured = collection.structure(doc(f'The order includes:\nOne new Lumen™ burn-in system, and\n{continuation} Horizon™ burn-in systems.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


@pytest.mark.parametrize('separator', [',', ';', '.', ''])
def test_unknown_equipment_list_continuation_cannot_be_dropped_without_conjunction(separator):
    structured = collection.structure(doc(f'The order includes:\nOne new Lumen™ burn-in system{separator}\nTwo more new Horizon™ burn-in systems.'))
    assert not structured['precursor_events'][0]['scope'].get('product')


@pytest.mark.parametrize('continuation', ['Two more new machines.', 'A second new machine.', 'One refurbished industrial machine.', 'Two cooling modules.'])
def test_unrecognized_item_identity_cannot_establish_list_uniqueness(continuation):
    structured = collection.structure(doc(f'The order includes:\nOne new Lumen™ burn-in system,\n{continuation}'))
    assert not structured['precursor_events'][0]['scope'].get('product')
