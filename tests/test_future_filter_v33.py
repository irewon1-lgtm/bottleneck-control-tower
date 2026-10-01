"""Design-derived cases only; no quality holdout labels are used here."""
import pytest

from bct.future_bottleneck import screen


@pytest.mark.parametrize('body', [
    'A customer signed a transformer purchase contract.',
    'Shipments increased following the installation program.',
    'The utility will install gas turbines for its new project.',
    'Demand for specialised care is growing.',
    'The retailer announced an investment in warehouse automation.',
    'New users adopted the service.',
])
def test_demand_changes_need_no_shortage_quantity_or_customer_name(body):
    result = screen(body)
    assert result['candidate'] and 'DEMAND' in result['discovery_paths']
    assert result['final_bottleneck'] is None
    assert not any(key in result for key in ('S1', 'S2', 'S3', 's_stage'))


@pytest.mark.parametrize('body', [
    'The factory will close next year.',
    'Production was suspended after the outage.',
    'Certification is delayed for the new components.',
    'Supplier access was restricted by export controls.',
    'Lead times remain extended for power transformers.',
    'A shortage of nurses is delaying additional capacity.',
])
def test_supply_path_operates_without_demand_growth(body):
    result = screen(body)
    assert result['candidate'] and 'SUPPLY' in result['discovery_paths']
    assert result['final_bottleneck'] is None


@pytest.mark.parametrize('body', [
    'A new supplier is offering qualified components.',
    'The plant is expanding production capacity.',
    'Alternative materials can substitute for the required components.',
    'Manufacturing yield and efficiency improved.',
    'Demand fell after orders were cancelled.',
    'The supply chain is normalizing.',
    'Lead times are shorter after the capacity expansion.',
])
def test_relief_path_is_independent_and_includes_demand_reversal(body):
    result = screen(body)
    assert result['candidate'] and 'RELIEF' in result['discovery_paths']


@pytest.mark.parametrize('body', [
    'Demand may grow if the contract is awarded.',
    'The plant plans an expansion.',
    'No production cuts are planned.',
    'A shortage of power transformers has not occurred.',
    'The conference states that manufacturing is expanding.',
])
def test_condition_plan_negation_and_ambiguous_statement_are_context_review(body):
    result = screen(body)
    assert result['candidate'] and result['decision'] == 'CONTEXT_REVIEW'
    assert result['context_review']


def test_tracked_material_bypasses_general_filter_without_semantic_promotion():
    body = 'General investor presentation.\nThe revised dossier covers NovaLT16.'
    assert not screen(body)['candidate']
    tracked = screen(body, tracked_terms=('NovaLT16',))
    assert tracked['candidate'] and tracked['discovery_paths'] == ['TRACKED_CHANGE']
    assert tracked['tracked_matches'] == ['NovaLT16']
    assert tracked['final_bottleneck'] is None
    assert not screen('NovaLT160 is unrelated.', tracked_terms=('NovaLT16',))['candidate']


def test_evidence_budget_is_shared_and_every_location_refers_to_full_body():
    body = ('Demand for power transformers may rise after the proposed installation project is confirmed.\n'
            'Production is delayed while the new plant is certified and alternative suppliers add capacity.\n'
            'Orders fell when customers cancelled projects, shortening the lead times.')
    result = screen(body)
    assert {'DEMAND', 'SUPPLY', 'RELIEF'} <= set(result['discovery_paths'])
    assert sum(len(excerpt.split()) for excerpts in result['evidence'].values() for excerpt in excerpts) <= 24
    assert result['quoted_word_count'] <= 24
    for locs in result['evidence_locations'].values():
        for loc in locs:
            assert body[loc['start']:loc['end']].strip()
            assert loc['paragraph'] == body.count('\n', 0, loc['start']) + 1
    for target in result['targets']:
        assert 'evidence' not in target
        loc = target['evidence_location']
        assert target['name'].lower() in body[loc['start']:loc['end']].lower()


def test_signal_at_end_of_long_body_is_preserved():
    body = ('The industry report lists routine names and locations.\n' * 400) + 'The plant will stop production in 2028.'
    result = screen(body)
    assert result['candidate'] and 'SUPPLY' in result['discovery_paths']
    assert result['evidence_locations']['SUPPLY'][0]['paragraph'] == 401


@pytest.mark.parametrize('body', [
    'The plant has capacity of 100 units and demand was 90 units.',
    'A software algorithm has a CPU bottleneck and reduced frame rates.',
    'The application was limited to brand sales and analytics.',
    'The operation may need shipment state, inventory and warehouse constraints. Workflow software gathers context.',
    'The report lists a project address and a contract identifier.',
])
def test_static_information_and_clear_digital_performance_noise_are_excluded(body):
    assert not screen(body)['candidate']


@pytest.mark.parametrize('body,path', [
    ('The company signed an agreement to develop a replacement product.', 'DEMAND'),
    ('The model sold fewer units; deliveries are down from the prior quarter.', 'RELIEF'),
    ('The funded development programme will bring the new mine online.', 'DEMAND'),
    ('The planned clinical trial was discontinued.', 'RELIEF'),
    ('Shipping services will return to the shorter transit route.', 'RELIEF'),
    ('The network restored access to alternative suppliers.', 'RELIEF'),
    ('Qualified production output increased at the larger operation.', 'RELIEF'),
    ('Workforce jobs were lost after the operation was halted.', 'SUPPLY'),
    ('The pediatric study is exploring a new treatment population.', 'DEMAND'),
])
def test_v33_general_action_synonyms_are_preserved_after_holdout_failure(body, path):
    # Previous live sample is now regression-only; new performance needs unseen data.
    result = screen(body)
    assert result['candidate'] and path in result['discovery_paths']
    assert result['final_bottleneck'] is None
