"""Session 5 source-local semantic extraction cannot imply qualified physical bottleneck."""
from hashlib import sha256

import pytest

from bct.future_semantic_shadow import analyze,public_receipt


def check(body, roles=None):
    data=analyze(body,document_id="SYNTHETIC-1",origin_url="https://example.org/synthetic",
                 body_status="FULL",provenance_verified=False)
    assert data["S1_S2_S3_assigned"] is False
    assert data["qualified_supply_comparison_ready"] is False
    assert data["research_usable_full_original"] is False
    assert data["body_sha256"]==sha256(body.encode()).hexdigest()
    for lead in data["literal_leads"]:
        pos=lead["locator"]
        assert body[pos["start"]:pos["end"]].startswith(lead["source_quote"])
        assert lead["target_stage"]=="NOT_ASSESSED"
        assert lead["source_fact_verified"] is False
        assert lead["supplier_qualification_verified"] is False
    if roles:
        for role in roles:assert data["literal_lead_counts"][role]>0
    return data


def test_committed_equipment_orders_are_leads_not_qualified_demand():
    value=check("Firm orders for power transformers increased to 120 units in 2028.",("DEMAND",))
    assert value["unknown_product_leads"] <= len(value["literal_leads"])


def test_delayed_qualification_is_supply_constraint_lead():
    d=check("Qualification of solid rocket motors was delayed until 2028.",("SUPPLY",))
    assert all(x["quantity"] is None for x in d["literal_leads"])


def test_halted_production_stays_supplier_constrained_not_bottleneck():
    d=check("Production of tungsten carbide was halted after the facility closed.",("SUPPLY",))
    assert d["S1_S2_S3_assigned"] is False


def test_expansion_is_relief_lead_not_independent_sufficiency():
    d=check("Qualified suppliers expanded production capacity for tungsten carbide.",("RELIEF",))
    assert all(x["supplier_qualification_verified"] is False for x in d["literal_leads"])


def test_future_plan_is_never_present_actual():
    d=check("Orders for gas turbines could increase to 120 units in 2028.",("DEMAND",))
    assert all(x["source_language_status"]=="CONDITIONAL_OR_NEGATED" and x["quantity"] is None
               for x in d["literal_leads"])


def test_cash_investment_is_not_product_capacity_quantity():
    d=check("The company invested $100 million. Orders for gas turbines increased to 120 units.")
    assert all(x["quantity"] is None for x in d["literal_leads"] if x["role"]=="SUPPLY")


def test_provenance_and_full_body_only_permit_research_use():
    body="Firm orders for gas turbines increased to 120 units."
    without=analyze(body,document_id="a",origin_url="https://example.org/a",
                    body_status="FULL",provenance_verified=False)
    with_provenance=analyze(body,document_id="a",origin_url="https://example.org/a",
                    body_status="FULL",provenance_verified=True)
    partial=analyze(body,document_id="a",origin_url="https://example.org/a",
                    body_status="PARTIAL",provenance_verified=True)
    assert not without["research_usable_full_original"]
    assert with_provenance["research_usable_full_original"]
    assert not partial["research_usable_full_original"]
    assert not with_provenance["S1_S2_S3_assigned"]


@pytest.mark.parametrize("body", [
    "Read more privacy policy cookies and advertising.",
    "New AI model improves inference speed and CPU latency.",
    "The factory announced a meeting about workforce culture.",
    "An investor forecasts share prices to increase next year.",
])
def test_no_supply_gap_conclusions_from_generic_prose(body):
    value=check(body)
    assert value["S1_S2_S3_assigned"] is False
    assert not value["qualified_supply_comparison_ready"]


def test_source_public_receipt_omits_any_excerpt_and_keeps_hash():
    d=check("Orders for gas turbines increased to 120 units.",("DEMAND",))
    safe=public_receipt(d)
    assert "literal_leads" not in safe
    assert safe["source_quote_redistributed"] is False
    assert safe["source_locators_only"] is True
    assert safe["body_sha256"]==d["body_sha256"]


def test_other_products_in_sentence_cannot_force_unique_product_binding():
    d=check("Orders for gas turbines and solid rocket motors increased to 120 units.",("DEMAND",))
    assert len(d["literal_leads"])>=1
    assert all(x["supplier_qualification_verified"] is False for x in d["literal_leads"])


def test_mixed_timeline_dates_do_not_become_qualified_gap():
    d=check("Orders for gas turbines increased to 120 units, needed by 2028-04-01.")
    assert all(x["target_stage"]=="NOT_ASSESSED" for x in d["literal_leads"])


@pytest.mark.parametrize("invalid", ["",None])
def test_blank_body_blocked(invalid):
    with pytest.raises(ValueError):
        analyze(invalid,document_id="a",origin_url="https://example.org/a")
