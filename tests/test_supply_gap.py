from copy import deepcopy

import pytest

from bct.supply_gap import evaluate


def claim(**kwargs):
    return {"basis": "Synthetic test fixture, not real evidence",
            "evidence": [{"url": "https://example.com/fixture", "published_on": "2026-09-01", "locator": "p1"}], **kwargs}


def fixture():
    dimension = dict(scope="qualified product / customer / region", unit="units",
                     period_start="2027-01-01", period_end="2027-12-31", balance_basis="total")
    return dict(current=claim(state="NOT_SHORT"),
                shortage_window=claim(start="2027-06-01", end="2027-09-01"),
                demand=claim(min=90, max=110, **dimension),
                supply=claim(min=60, max=75, kind="QUALIFIED_DELIVERABLE", coverage="ALL_FEASIBLE_SUPPLIERS", **dimension),
                relief=claim(review_complete=True))


def test_range_and_objective_separate_from_investment():
    result = evaluate(fixture(), "2026-10-01")
    assert result["gap_range"] == [15, 50]
    assert result["objective_fit"] == "FUTURE_MATCH"
    assert result["investment_status"] == "UNRESOLVED"


@pytest.mark.parametrize("change,expected", [(dict(min=80, max=120), "GAP_CONDITIONAL"),
                                              (dict(min=120, max=140), "NO_GAP_IN_RANGE")])
def test_overlap_and_supply_relief(change, expected):
    data = fixture()
    data["supply"].update(change)
    result = evaluate(data, "2026-10-01")
    assert result["gap_status"] == expected
    assert result["objective_fit"] != "FUTURE_MATCH"


@pytest.mark.parametrize("field,value", [("unit", "MW"), ("scope", "other grade"),
    ("period_end", "2028-12-31"), ("balance_basis", "incremental_free"),
    ("coverage", "ONE_SUPPLIER"), ("kind", "NAMEPLATE"), ("min", None),
    ("max", float("nan")), ("min", True), ("min", 80), ("evidence", [])])
def test_mismatch_missing_and_partial_supply_cannot_confirm(field, value):
    data = fixture()
    data["supply"][field] = value
    assert evaluate(data, "2026-10-01")["gap_status"] == "UNRESOLVED"


def test_timing_route_needs_all_supply_and_future_need():
    data = fixture()
    data.pop("demand")
    data.pop("supply")
    data["timing"] = claim(required_by="2027-06-01", earliest_qualified_supply="2028-01-01", coverage="ALL_FEASIBLE_SUPPLIERS")
    assert evaluate(data, "2026-10-01")["objective_fit"] == "FUTURE_MATCH"
    data["timing"]["coverage"] = "ONE_NEW_FACTORY"
    assert evaluate(data, "2026-10-01")["gap_status"] == "UNRESOLVED"


def test_current_unknown_and_horizon_are_not_hidden_future():
    data = fixture()
    data["current"] = claim(state="SHORT")
    assert evaluate(data, "2026-10-01")["objective_fit"] == "CURRENT_REFERENCE"
    data["current"] = claim(state="UNRESOLVED")
    assert evaluate(data, "2026-10-01")["objective_fit"] == "UNRESOLVED"
    data = fixture()
    data["shortage_window"] = claim(start="2029-01-01", end="2029-12-31")
    assert evaluate(data, "2026-10-01")["objective_fit"] == "OUTSIDE_WINDOW"


def test_missing_inputs_and_future_dated_evidence_and_no_mutation():
    assert evaluate({}, "2026-10-01")["gap_range"] is None
    data = fixture()
    data["demand"]["evidence"][0]["published_on"] = "2026-10-02"
    original = deepcopy(data)
    assert evaluate(data, "2026-10-01")["gap_status"] == "UNRESOLVED"
    assert data == original
    assert evaluate(fixture(), "2028-02-29")


def test_relief_incomplete_and_conflicting_quantity_timing_block_promotion():
    data = fixture()
    data["relief"]["review_complete"] = False
    assert evaluate(data, "2026-10-01")["objective_fit"] == "UNRESOLVED"
    data = fixture()
    data["supply"].update(min=120, max=140)
    data["timing"] = claim(required_by="2027-06-01", earliest_qualified_supply="2028-01-01", coverage="ALL_FEASIBLE_SUPPLIERS")
    assert evaluate(data, "2026-10-01")["gap_status"] == "UNRESOLVED"


def test_future_quantity_period_cannot_prove_earlier_shortage():
    data = fixture()
    for key in ("demand", "supply"):
        data[key].update(period_start="2030-01-01", period_end="2030-12-31")
    assert evaluate(data, "2026-10-01")["objective_fit"] != "FUTURE_MATCH"


@pytest.mark.parametrize("route", ["quantity", "timing"])
@pytest.mark.parametrize("window", [{}, {"start": None, "end": None},
    {"start": None, "end": "2027-09-01"},
    {"start": "2027-06-01", "end": None},
    {"start": "invalid", "end": "2027-09-01"}])
def test_missing_or_invalid_window_preserves_gap_without_future_confirmation(route, window):
    data = fixture()
    if route == "timing":
        data.pop("demand")
        data.pop("supply")
        data["timing"] = claim(required_by="2027-06-01",
            earliest_qualified_supply="2028-01-01", coverage="ALL_FEASIBLE_SUPPLIERS")
    data["shortage_window"] = claim(**window)
    original = deepcopy(data)
    result = evaluate(data, "2026-10-01")
    assert result["gap_status"] == "GAP_SUPPORTED"
    assert result["objective_fit"] == "UNRESOLVED"
    assert "향후 24개월 이내 부족 발생 시점 미확인 또는 범위 밖" in result["blockers"]
    assert data == original
