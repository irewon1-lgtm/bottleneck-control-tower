"""Small body-context regressions from the stage 11 manual review."""
import pytest

from bct.future_bottleneck import screen


@pytest.mark.parametrize("body", [
    'Labor disruption was the final straw. "The nationwide shortage woke us up," recalls the operations director. Retention rates were low and headcount could not be maintained.',
    'Manufacturers manage product repairs. Handling repairs can become a bottleneck, leading to delays. Repair operations need skilled technicians and parts inventories. Balancing resources to avoid overstocking or shortages is a continual challenge.',
    'Inventory managers use software to prevent shortages. Demand for automation is growing.',
])
def test_generic_prevention_and_labor_context_are_not_supply_pressure(body):
    assert not screen(body)["candidate"]


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
