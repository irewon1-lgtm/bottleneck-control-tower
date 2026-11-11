"""Authored grammar regressions; preserved real-source evidence runs separately."""
import pytest
from bct import precursor_collection as collection, precursor_scope_reader as reader
from test_precursor_source_pipeline import doc


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
