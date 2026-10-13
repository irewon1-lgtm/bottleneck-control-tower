"""Stage-2 exact-source and advisory safety tests, not a performance benchmark."""
from copy import deepcopy
import hashlib
import json

import pytest

from bct.v4.free_ai import (APIError, GROQ_SCHEMA, QUOTE_SCHEMA, SYSTEM, Router, source_input,
                            validate_output, validate_reading)
from bct.v4.store import Ledger
from test_v4_free_ai import ENV, Fake, config, document, router


def reading(doc, entity="NovaLT16", kind="PHYSICAL_PRODUCT", role="DEMAND_INCREASE", actuality="ACTUAL"):
    return {"items": [{"kind": kind, "role": role, "actuality": actuality,
        "context": {"quote": doc["body"]},
        "entity": {"value": entity, "quote": doc["body"]}, "facts": []}]}


def validate(doc, data):
    return validate_reading(json.dumps(data), doc, source_input(doc, config(), ENV))


def test_compatibility_coordinates_are_untrusted_and_internal_validator_stays_strict():
    def visit(value):
        if isinstance(value, dict):
            assert not set(value.get("properties", {})) & {"start", "end"}
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(QUOTE_SCHEMA)
    assert "Use zero for all start/end" in SYSTEM
    assert set(GROQ_SCHEMA["properties"]["items"]["items"]["properties"]["context"]["properties"]) == {"quote", "start", "end"}
    doc = document(body="Buyer signed an order for NovaLT16.")
    result = validate(doc, reading(doc))
    item = result["items"][0]
    assert item["context"]["start"] == 0
    assert item["context"]["end"] == len(doc["body"])
    assert item["context"]["reference"]["source_quote"] == doc["body"]
    assert item["coordinate_origin"] == "PYTHON_EXACT_UNIQUE_QUOTE"
    assert item["context"]["reference"]["published_at"] == doc["published_at"]
    assert item["s_stage"] == "UNKNOWN" and not item["forecast_candidate"]
    wrong = deepcopy(item)
    # The existing positioned validator still rejects a wrong range.
    raw = {k: wrong[k] for k in ("kind", "role", "actuality", "context", "entity", "facts")}
    for f in (raw["context"], raw["entity"]): f.pop("reference", None)
    raw["context"]["end"] -= 1
    with pytest.raises(APIError, match="SOURCE"):
        validate_output(json.dumps({"items": [raw]}), doc, source_input(doc, config(), ENV))
    # Deliberately false legacy/model coordinates cannot affect Python binding.
    data = reading(doc)
    for f in (data["items"][0]["context"], data["items"][0]["entity"]):
        f.update(start=-900, end=900000)
    rebound = validate(doc, data)["items"][0]
    assert rebound["context"]["start"] == 0 and rebound["context"]["end"] == len(doc["body"])


@pytest.mark.parametrize("quote,value,reason", [
    ("Buyer signed an order for NovaLT16!", "NovaLT16", "QUOTE_NOT_IN_SOURCE"),
    ("Buyer signed an order for NovaLT16.", "NOVALT16", "VALUE_NOT_LITERAL"),
    ("Buyer signed an order for NovaLT16.", "OtherModel", "VALUE_NOT_LITERAL"),
    ("", "NovaLT16", "VALUE_NOT_LITERAL"),
])
def test_fabricated_quotes_aliases_and_case_are_rejected(quote, value, reason):
    doc = document(body="Buyer signed an order for NovaLT16.")
    data = reading(doc)
    data["items"][0]["entity"].update(quote=quote, value=value)
    result = validate(doc, data)
    assert not result["items"] and result["source_status"] == "REVIEW_REQUIRED"
    assert result["rejected_items"][0]["reason"] == reason


def test_unicode_punctuation_is_not_fuzzy_matched():
    doc = document(body="Westinghouse’s nuclear reactor technologies are being developed.")
    data = reading(doc, "Westinghouse’s nuclear reactor technologies", kind="UNKNOWN", role="UNKNOWN")
    assert validate(doc, data)["source_status"] == "PASS"
    data["items"][0]["entity"]["value"] = "Westinghouse's nuclear reactor technologies"
    assert validate(doc, data)["rejected_items"][0]["reason"] == "VALUE_NOT_LITERAL"


def test_duplicate_quote_is_held_even_with_claimed_legacy_position():
    line = "Buyer signed an order for NovaLT16."
    doc = document(body=line + "\n" + line)
    data = reading(doc)
    data["items"][0]["context"] = {"quote": line, "start": 0, "end": len(line)}
    data["items"][0]["entity"].update(start=0, end=len(doc["body"]))
    result = validate(doc, data)
    assert not result["items"]
    assert result["rejected_items"][0]["reason"] == "AMBIGUOUS_QUOTE"


def test_quote_in_original_but_outside_sent_windows_is_held():
    doc = document(body="Buyer signed an order for NovaLT16.\nUnselected evidence elsewhere.")
    selected = source_input(doc, config(), ENV)
    selected["windows"] = [selected["windows"][0]]
    data = reading(doc)
    data["items"][0]["context"]["quote"] = "Unselected evidence elsewhere."
    assert validate_reading(json.dumps(data), doc, selected)["rejected_items"][0]["reason"] == "QUOTE_OUTSIDE_INPUT"


@pytest.mark.parametrize("mutation", ["body", "window"])
def test_hash_or_selected_text_mismatch_prevents_revalidation(mutation):
    doc = document(body="Buyer signed an order for NovaLT16.")
    data = reading(doc); selected = source_input(doc, config(), ENV)
    if mutation == "body": doc["body"] += " altered"
    else: selected["windows"][0]["text"] = "altered"
    with pytest.raises(APIError, match="INPUT_INVALID"):
        validate_reading(json.dumps(data), doc, selected)


@pytest.mark.parametrize("with_evidence", [False, True])
def test_unknown_requires_empty_evidence_and_remains_unknown(with_evidence):
    doc = document(body="Buyer signed an order for NovaLT16.")
    data = reading(doc)
    data["items"][0]["facts"] = [{"field": "supply_pool", "value": None,
                                   "quote": doc["body"] if with_evidence else ""}]
    result = validate(doc, data)
    if with_evidence:
        assert result["rejected_items"][0]["reason"] == "NULL_WITH_EVIDENCE"
    else:
        item = result["items"][0]
        assert item["facts"][0]["start"] == item["facts"][0]["end"] == 0
        assert item["target"]["supply_pool"] is None
        assert item["semantic_status"] == "UNKNOWN_REQUIRES_REVIEW"


@pytest.mark.parametrize("entity,model_kind,expected", [
    ("advanced light-water SMRs", "PROJECT", "PRODUCT_FAMILY"),
    ("small modular reactors", "GENERAL_EXPRESSION", "PRODUCT_FAMILY"),
    ("Advanced Nuclear Fuel Line Pilot Projects", "PRODUCT_FAMILY", "PROJECT"),
])
def test_literal_product_head_and_project_head_are_separate(entity, model_kind, expected):
    doc = document(body="The department selected " + entity + ".")
    item = validate(doc, reading(doc, entity, kind=model_kind))["items"][0]
    assert item["kind"] == expected and item["model_classification"]["kind"] == model_kind
    assert item["physical_exploration_lead"] == (expected == "PRODUCT_FAMILY")
    assert bool(item["target"]["product"]) == (expected == "PRODUCT_FAMILY")
    assert item["role"] == "UNKNOWN" and not item["forecast_candidate"]


@pytest.mark.parametrize("body,role,expected_role,actuality", [
    ("The department awarded $800 million to advance NovaLT16 production.", "SUPPLY_INCREASE", "UNKNOWN", "ACTUAL"),
    ("The department awarded $800 million in grants under a contract for NovaLT16 development.", "DEMAND_INCREASE", "UNKNOWN", "ACTUAL"),
    ("The government established a strategic partnership to accelerate NovaLT16 development.", "SUPPLY_INCREASE", "UNKNOWN", "ACTUAL"),
    ("The government established a strategic partnership for NovaLT16.", "DEMAND_INCREASE", "UNKNOWN", "ACTUAL"),
    ("Buyer signed an order for NovaLT16.", "DEMAND_INCREASE", "DEMAND_INCREASE", "ACTUAL"),
    ("Buyer plans to sign an order for NovaLT16.", "DEMAND_INCREASE", "UNKNOWN", "PLAN"),
    ("Buyer expects orders for NovaLT16 in 2028.", "DEMAND_INCREASE", "UNKNOWN", "FORECAST"),
    ("Buyer did not sign an order for NovaLT16.", "DEMAND_INCREASE", "UNKNOWN", "NEGATED"),
    ("Buyer has NOT signed an order for NovaLT16.", "DEMAND_INCREASE", "UNKNOWN", "NEGATED"),
    ("NovaLT16 production capacity expanded by 20%.", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "ACTUAL"),
    ("The company plans to expand NovaLT16 production capacity.", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "PLAN"),
    ("The company forecasts NovaLT16 production capacity will increase.", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "FORECAST"),
    ("The company commissioned a NovaLT16 production line.", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "ACTUAL"),
    ("The company will commission a NovaLT16 production line.", "SUPPLY_INCREASE", "UNKNOWN", "PLAN"),
    ("Supplier delivered 20 NovaLT16 turbines.", "SUPPLY_INCREASE", "UNKNOWN", "ACTUAL"),
    ("NovaLT16 production was delayed by six months.", "SUPPLY_DELAY", "SUPPLY_DELAY", "ACTUAL"),
    ("NovaLT16 annual revenue increased.", "SUPPLY_INCREASE", "UNKNOWN", "UNKNOWN"),
    ("The executive order mentions NovaLT16.", "DEMAND_INCREASE", "UNKNOWN", "UNKNOWN"),
    ("Buyer signed an order for NovaLT16; it plans to expand production capacity.", "DEMAND_INCREASE", "DEMAND_INCREASE", "ACTUAL"),
    ("Buyer signed an order for NovaLT16; it plans to expand production capacity.", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "PLAN"),
])
def test_physical_event_counterexamples(body, role, expected_role, actuality):
    doc = document(body=body)
    item = validate(doc, reading(doc, role=role))["items"][0]
    assert item["role"] == expected_role and item["actuality"] == actuality
    assert item["semantic_status"] == "UNKNOWN_REQUIRES_REVIEW"
    assert item["s_stage"] == "UNKNOWN" and not item["forecast_candidate"]


def test_bad_item_is_rejected_without_fabricating_a_good_item():
    doc = document(body="Buyer signed an order for NovaLT16.")
    data = reading(doc)
    bad = deepcopy(data["items"][0]); bad["entity"]["value"] = "OtherModel"
    data["items"].append(bad)
    result = validate(doc, data)
    assert result["source_status"] == "PARTIAL_REVIEW"
    assert len(result["items"]) == len(result["rejected_items"]) == 1


def test_quote_only_router_cache_retains_machine_coordinates_on_restart(tmp_path):
    doc = document(body="Buyer signed an order for NovaLT16.")
    fake = Fake({"groq": {"text": json.dumps(reading(doc)), "usage": {"total_tokens": 20}, "headers": {}}})
    ledger = Ledger(tmp_path); ledger.capture(doc)
    with ledger.worker():
        r = router(ledger, fake)
        first = r.read(doc)
    ledger.close(); ledger = Ledger(tmp_path)
    with ledger.worker():
        second = router(ledger, fake, run="restart").read(doc)
    assert first["status"] == second["status"] == "PASS" and second["cached"]
    assert fake.calls == ["groq"]
    assert first["result"]["items"][0]["context"] == second["result"]["items"][0]["context"]
    assert ledger.db.execute("SELECT COUNT(*) FROM events WHERE kind='API_VALIDATION'").fetchone()[0] == 1
    ledger.close()


def test_partial_source_result_is_stored_as_review_without_a_repair_call(tmp_path):
    doc = document(body="Buyer signed an order for NovaLT16.")
    data = reading(doc);bad = deepcopy(data["items"][0]);bad["entity"]["value"] = "NotInOriginal"
    data["items"].append(bad)
    fake = Fake({"groq": {"text": json.dumps(data), "usage": {"total_tokens": 20}, "headers": {}}})
    ledger = Ledger(tmp_path)
    assert router(ledger, fake).read(doc)["status"] == "REVIEW_REQUIRED"
    assert router(ledger, fake, run="restart").read(doc)["status"] == "REVIEW_REQUIRED"
    audit = json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='API_VALIDATION'").fetchone()[0])
    assert len(audit["result"]["items"]) == len(audit["result"]["rejected_items"]) == 1
    assert fake.calls == ["groq"]
    assert not ledger.db.execute("SELECT 1 FROM events WHERE kind='API_RESPONSE'").fetchone()
    ledger.close()
