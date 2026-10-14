"""Authored counterexamples and metric arithmetic, not official corpus gold."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from bct.v4.free_ai import source_input, validate_reading
from scripts.v4.accuracy_review import assess, check_gold, observation, ratios
from test_v4_free_ai import ENV, config, document
from test_v4_semantics import check, proposal, value


@pytest.mark.parametrize("entity,region", [
    ("battery cells", "Germany"), ("optical transceivers", "Japan"),
    ("industrial heat pumps", "United Kingdom"), ("Class 8 trucks", "North America"),
])
def test_missing_region_is_added_only_from_a_literal_product_relation(entity, region):
    body = f"The ministry awarded funding to advance {region} deployment of {entity}."
    item = check(body, entity, (("region", None),), role="SUPPLY_INCREASE")
    assert value(item, "region") == region
    fact = next(f for f in item["facts"] if f["field"] == "region")
    assert body[fact["start"]:fact["end"]] == fact["quote"]
    assert fact["reference"] and fact["semantic_actuality"] == "PLAN"
    assert item["source_literal_additions"] == ["region"]
    assert item["role"] == "UNKNOWN" and item["s_stage"] == "UNKNOWN"


@pytest.mark.parametrize("body,entity", [
    ("The ministry supported Acme deployment of battery cells.", "battery cells"),
    ("The manufacturer headquartered in Germany received funding for battery cells.", "battery cells"),
    ("Japan deployment of optical transceivers; funding for battery cells was awarded.", "battery cells"),
    ("The ministry supported Germany deployment of battery cells and Japan deployment of battery cells.", "battery cells"),
    ("The ministry did not support Germany deployment of battery cells.", "battery cells"),
    ("The ministry supported Germany deployment of the Solar Factory Expansion Project.", "Solar Factory Expansion Project"),
])
def test_missing_regions_are_not_inferred_from_parties_other_products_or_ambiguity(body, entity):
    item = check(body, entity)
    assert value(item, "region") is None and item["target"]["region"] is None


def test_existing_region_claim_is_not_replaced_by_supplementation():
    item = check("The order specifies Japan delivery of optical transceivers for deployment in Germany.",
                 "optical transceivers", (("region", "Germany"),))
    assert value(item, "region") == "Germany" and item["source_literal_additions"] == []


def test_new_region_cannot_bypass_existing_exact_quote_guard():
    quote = "Funding was awarded to advance Germany deployment of battery cells."
    doc = document(body=quote + "\n" + quote)
    result = validate_reading(json.dumps(proposal(quote, "battery cells")), doc,
                              source_input(doc, config(), ENV))
    assert result["source_status"] == "REVIEW_REQUIRED"
    assert result["items"] == [] and result["rejected_items"][0]["reason"] == "AMBIGUOUS_QUOTE"


def test_supplementation_cannot_hide_invalid_original_null_evidence():
    body = "Funding was awarded to advance Germany deployment of battery cells."
    doc = document(body=body)
    data = proposal(body, "battery cells", (("region", None),))
    data["items"][0]["facts"][0]["quote"] = body
    result = validate_reading(json.dumps(data), doc, source_input(doc, config(), ENV))
    assert result["source_status"] == "REVIEW_REQUIRED" and result["items"] == []
    assert result["rejected_items"][0]["reason"] == "NULL_WITH_EVIDENCE"


def test_wrong_known_value_counts_false_positive_and_missed_truth():
    counts = ratios(observation("Germany", "Japan"))
    assert (counts["TP"], counts["FP"], counts["FN"]) == (0, 1, 1)
    assert counts["precision"] == counts["recall"] == counts["f1"] == 0


def test_truth_absent_unknown_has_no_positive_denominator():
    counts = ratios(observation(None, None))
    assert counts["UNKNOWN"] == counts["truth_absent_unknown"] == 1
    assert counts["precision"] is counts["recall"] is counts["f1"] is None


def test_all_unknown_cannot_score_perfect_recall_on_known_truth():
    counts = ratios(observation("Germany", None))
    assert counts["known_truth_missed"] == counts["FN"] == 1
    assert counts["precision"] is None and counts["recall"] == counts["f1"] == 0


def test_duplicate_outputs_cannot_inflate_scoped_accuracy():
    gold = {"rows": [{"id": "one", "quote": "one", "expected": {"product": "cells"}}],
            "exploration_mentions": []}
    item = {"context": {"quote": "one"}}
    with pytest.raises(ValueError, match="AMBIGUOUS_GOLD_CONTEXT_ASSOCIATION"):
        assess([item, item], gold)


def test_product_and_project_in_same_source_context_have_separate_denominators():
    gold = {"rows": [
        {"id": "project", "quote": "one", "match_entity": "Fuel Pilot Project", "expected": {"product": None}},
        {"id": "fuel", "quote": "one", "match_entity": "nuclear fuel", "expected": {"product": "nuclear fuel"}},
    ], "exploration_mentions": []}
    project = {"context": {"quote": "one"}, "entity": {"value": "Fuel Pilot Project"}, "kind": "PROJECT"}
    fuel = {"context": {"quote": "one"}, "entity": {"value": "nuclear fuel"}, "kind": "PRODUCT_FAMILY"}
    missing = assess([project], gold)["micro"]
    found = assess([project, fuel], gold)["micro"]
    assert missing["FN"] == 1 and missing["recall"] == 0
    assert missing["UNKNOWN"] == 1 and missing["unreturned_record_positive_fields"] == 1
    assert found["TP"] == 1 and found["FP"] == found["FN"] == 0
    assert found["precision"] == found["recall"] == 1


def test_incorrect_entity_inside_gold_context_counts_fp_and_fn():
    gold = {"rows": [{"id": "product", "quote": "one", "match_entity": "battery cells",
                       "expected": {"product": "battery cells"}}], "exploration_mentions": []}
    wrong = {"context": {"quote": "one"}, "entity": {"value": "Acme"},
             "kind": "PHYSICAL_PRODUCT", "role": "UNKNOWN", "facts": []}
    result = assess([wrong], gold)
    assert result["micro"]["FP"] == result["micro"]["FN"] == 1
    assert result["micro"]["precision"] == result["micro"]["recall"] == 0
    assert result["unscored_predictions"] == []


def test_gold_is_bound_to_source_and_declared_input():
    gold = json.loads(Path("docs/v4/STAGE4_GOLD.json").read_text())
    doc = json.loads(Path("tests/fixtures/v4_stage3_official_source.json").read_text())["document"]
    check_gold(gold, doc)
    changed = deepcopy(gold); changed["rows"][0]["start"] += 1
    with pytest.raises(ValueError, match="GOLD_QUOTE_MISMATCH"):
        check_gold(changed, doc)
    with pytest.raises(ValueError, match="GOLD_SOURCE_HASH_MISMATCH"):
        check_gold(gold, {**doc, "body": doc["body"] + " altered"})
