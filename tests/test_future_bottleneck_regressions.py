"""Small body-context regressions from the stage 11 manual review."""
import pytest

from bct.future_bottleneck import screen


@pytest.mark.parametrize("body", [
    'Labor disruption was the final straw. "The nationwide shortage woke us up," recalls the operations director. Retention rates were low and headcount could not be maintained.',
    'Manufacturers manage product repairs. Handling repairs can become a bottleneck, leading to delays. Repair operations need skilled technicians and parts inventories. Balancing resources to avoid overstocking or shortages is a continual challenge.',
    'Inventory managers use software to prevent shortages. Demand for automation is growing.',
])
def test_v33_ambiguous_and_workforce_material_is_preserved_for_context(body):
    # Broader intake preserves these leads; it makes no supply relationship claim.
    result = screen(body)
    assert result["candidate"]
    assert result["final_bottleneck"] is None


@pytest.mark.parametrize("body", [
    'Freight demand is growing. The capacity crunch is already showing up during the fall peak shipping season. Trucking rates are increasing.',
    'Drivers are in shortage. Some trucking companies are reducing capacity because they lack working capital. Cross-border freight volume is increasing.',
    'A shortage of workers and power transformers delays manufacturing.',
    'Power transformers could become a bottleneck as demand grows. Capacity is limited until 2028.',
])
def test_physical_capacity_pressure_survives_labor_and_conditional_context(body):
    result = screen(body)
    assert result["candidate"]
    assert result["final_bottleneck"] is None


def test_lpg_usage_clause_does_not_become_a_target():
    result = screen('India has been suffering acute shortage of LPG, used for cooking and industrial processes.')
    assert result["candidate"]
    assert [x["name"] for x in result["targets"]] == ["LPG"]


def test_transport_capacity_rule_does_not_capture_compute_capacity():
    assert not screen('Reduced capacity in a software database slows AI workflows. Demand for faster queries is growing.')["candidate"]


@pytest.mark.parametrize("body", [
    'AI improves manufacturing output.The conference discusses analytics.The application was limited to brand sales.The platform has expanded data analysis.',
    'The operation may need shipment state, inventory, customer priority, warehouse constraints. Workflow software collects context before a decision.',
])
def test_stage_11_digital_and_event_false_positives_are_excluded(body):
    result = screen(body)
    assert not result["candidate"]
    assert result["targets"] == []
    assert result["final_bottleneck"] is None


def test_v33_ambiguous_manufacturing_expansion_is_context_review():
    result = screen('Manufacturing is expanding.The conference explores digital research.Partners include Example Labs Private Limited.The program lists presentations.')
    assert result['candidate'] and result['decision'] == 'CONTEXT_REVIEW'
    assert result['targets'] == [] and result['final_bottleneck'] is None


@pytest.mark.parametrize("body,target", [
    ('AI improves factory planning.Power transformers have lead times of 24 months.A new plant is planned.', 'power transformers'),
    ('The event discusses gas turbines.Production capacity is limited for 24 months.A new plant is planned.', 'gas turbines'),
    ('The operation may need inventory and warehouse constraints to decide. Workflow software gathers context. A shortage of power transformers delays manufacturing.', 'power transformers'),
    ('The operation may need sapphire optical windows amid a shortage of sapphire optical windows. Workflow software tracks production delays.', 'sapphire optical windows'),
])
def test_digital_or_event_context_preserves_real_supply_pressure(body, target):
    result = screen(body)
    assert result["candidate"]
    assert target in [t["name"].lower() for t in result["targets"]]
    assert result["final_bottleneck"] is None
