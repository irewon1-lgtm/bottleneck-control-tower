"""Development/synthetic relation checks, never a reused holdout accuracy test."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from bct.v4.research_adapter import analyze
from test_precursor_source_pipeline import doc
from test_precursor_evidence_graph import pair, ASOF
from test_v4_repair import proposal


def reading(body, entity, role="SUPPLY_INCREASE", *, entity_quote=None):
    d = doc(body, "Forge", url="https://forge.example/press-release/order")
    item = {"kind": "PHYSICAL_PRODUCT", "role": role, "actuality": "ACTUAL",
            "context": {"quote": body}, "entity": {"value": entity, "quote": entity_quote or body}, "facts": []}
    p = {"text": json.dumps({"items": [item]}),
         "source": {"windows": [{"start": 0, "end": len(body), "text": body}]}}
    r = analyze([d], {d["document_id"]: p}, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    return r


@pytest.mark.parametrize("model", ["NovaLT16", "Helios24", "RX-ZZ"])
def test_model_prefix_is_not_a_literal_product_identity(model):
    r = reading(f"Forge received new orders for {model}0 machines.", model)
    assert not r["product_exploration"] and not r["forwarded_events"]
    assert any("PRODUCT_TOKEN_BOUNDARY" in h["reason"] for h in r["held"])


@pytest.mark.parametrize("product", ["NovaLT16", "optical transceivers", "battery cells"])
def test_order_for_production_equipment_is_not_an_order_for_its_output(product):
    r = reading(f"Forge received new orders for machines used to manufacture {product}.", product)
    assert r["product_exploration"]  # a real product mention remains searchable
    assert not r["forwarded_events"] and not r["candidates"]
    assert any("UNPROVEN_DEMAND_OBJECT" in h["reason"] for h in r["held"])


@pytest.mark.parametrize("entity", ["NovaLT16", "gas turbines", "battery cells"])
def test_explicit_order_remains_demand_with_future_output_capacity(entity):
    r = reading(f"Forge received new orders for {entity} equipment, which will expand production capacity for laser chips.", entity)
    assert len(r["forwarded_events"]) == 1, r["held"]
    event = r["forwarded_events"][0]
    assert event["role"] == "DEMAND" and event["advisory_role"] == "DEMAND_INCREASE"
    assert event["adapter_role_resolution"]["raw_model_role"] == "SUPPLY_INCREASE"
    assert r["counts"]["supply_signals"] == 0 and not r["candidates"]
    assert any(event["event_id"] in o.get("event_ids", []) for o in r["engine"]["observations"])


def test_order_with_physical_count_is_preserved_without_copying_ai_quantities():
    r = reading("Forge received new orders for 24 gas turbines.", "gas turbines")
    assert len(r["forwarded_events"]) == 1 and r["counts"]["supply_signals"] == 0


def test_existing_unsupported_target_grammar_stays_exploration_only():
    r = reading("Forge received new orders for industrial heat pumps.", "industrial heat pumps")
    assert r["product_exploration"] and not r["forwarded_events"]
    assert any("EXISTING_PHYSICAL_TARGET_GRAMMAR_UNSUPPORTED" in h["reason"] for h in r["held"])


def test_other_product_future_output_year_is_not_this_order_need_time():
    r = reading("Forge signed firm new orders for NovaLT16 equipment, which will expand production capacity for laser chips in 2028.", "NovaLT16")
    e = r["forwarded_events"][0]
    assert e["role"] == "DEMAND" and e["window"] is None
    assert e["adapter_unattributed_window"]["text"] == "2028"
    assert e["temporal_facts"]["periods"][0]["fact_kind"] == "UNATTRIBUTED_PERIOD"
    assert not r["candidates"]


def test_explicit_equipment_delivery_period_is_preserved():
    r = reading("Forge signed firm new orders for NovaLT16 equipment, which will expand production capacity for laser chips; NovaLT16 delivery required in 2028.",
                "NovaLT16", entity_quote="orders for NovaLT16 equipment")
    assert r["forwarded_events"], r["held"]
    e = r["forwarded_events"][0]
    assert e["role"] == "DEMAND" and e["window"]["text"] == "2028"
    assert any(p["fact_kind"] == "DEMAND_NEED" for p in e["temporal_facts"]["periods"])


@pytest.mark.parametrize("qualifier", ["plans to receive", "did not receive", "expects to receive"])
def test_uncommitted_or_negated_order_cannot_become_actual_demand(qualifier):
    r = reading(f"Forge {qualifier} new orders for NovaLT16 equipment.", "NovaLT16")
    assert not r["forwarded_events"] and not r["candidates"]


def test_real_development_fox_xp_reaches_engine_as_demand_without_invented_supply():
    data = Path(__file__).resolve().parents[1] / "docs/v4/stage4-corpus"
    record = next(r for r in json.loads((data/"groq-responses-repair-v1.json").read_text())["documents"]
                  if r["split"] == "development")
    row = next(r for r in json.loads((data/"safe-inputs-v1.json").read_text())["documents"]
               if r["document_id"] == record["document_id"])
    metadata = next(r for r in json.loads((data/"manifest.json").read_text())["documents"]
                    if r["document_id"] == record["document_id"])
    d = doc(Path(metadata["body_path"]).read_text(), "Aehr", url=metadata["url"])
    d.update(document_id=record["document_id"], body_sha256=row["body_sha256"])
    p = {"text": record["response"]["text"], "source": row["source"]}
    before = deepcopy((d, p))
    r = analyze([d], {d["document_id"]: p}, enabled=True, mode="BACKFILL", as_of=ASOF)
    assert before == (d, p)
    assert len(r["forwarded_events"]) == 1
    e = r["forwarded_events"][0]
    assert e["scope"]["product"]["value"] == "FOX-XP" and e["role"] == "DEMAND"
    assert e["adapter_role_resolution"]["raw_model_role"] == "SUPPLY_INCREASE"
    assert e["adapter_role_resolution"]["source_checked_role"] == "DEMAND_INCREASE"
    assert e["demand_status"] == "UNKNOWN" and e["window"] is None
    assert not e["qualified"] and e["quantity"] == "UNKNOWN" and not r["candidates"]
    assert r["counts"]["engine_observations_with_AI_events"] == 1


@pytest.mark.parametrize("change", ["specification", "region", "customer", "issuer", "period", "relief"])
def test_existing_target_independence_time_relief_contracts_are_preserved(change):
    docs = list(pair())
    if change == "specification":
        docs[1]["body"] = docs[1]["body"].replace("military-grade", "industrial")
    elif change == "region":
        docs[1]["body"] += " The military-grade tungsten is for military drones in Germany under contract K-242."
    elif change == "customer":
        docs[1]["body"] += " The military-grade tungsten is for industrial buyers in United States under contract K-242."
    elif change == "issuer":
        docs[1]["origin_publisher"] = docs[0]["origin_publisher"]
    elif change == "period":
        docs = list(pair(ready="2027"))
    else:
        docs[1]["body"] += " Qualified inventory of military-grade tungsten covers all contracted demand."
    for d in docs:
        d["body_sha256"] = hashlib.sha256(d["body"].encode()).hexdigest()
    p = {docs[0]["document_id"]: proposal(docs[0], "DEMAND_INCREASE")}
    r = analyze(docs, p, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert not r["candidates"]


def test_existing_positive_target_connection_still_works():
    docs = list(pair())
    r = analyze(docs, {docs[0]["document_id"]: proposal(docs[0], "DEMAND_INCREASE")},
                enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert r["candidates"] and r["forwarded_events"]
    assert all(x["research_only"] and x["s_stage"] == "UNKNOWN" for x in r["candidates"])


@pytest.mark.parametrize("failure", ["AMBIGUOUS_QUOTE", "QUOTE_NOT_IN_SOURCE", "SOURCE", "NULL_WITH_EVIDENCE"])
def test_diagnostics_preserve_rejections_and_expose_the_exact_cause(failure):
    from bct.v4.quote_diagnostics import diagnose
    body = "Forge received an order for NovaLT16. NovaLT16 was mentioned twice."
    d = doc(body, "Forge", url="https://forge.example/press-release/order")
    item = {"kind": "PHYSICAL_PRODUCT", "role": "DEMAND_INCREASE", "actuality": "ACTUAL",
            "context": {"quote": body}, "entity": {"value": "NovaLT16", "quote": body}, "facts": []}
    if failure == "AMBIGUOUS_QUOTE":
        item["entity"]["quote"] = "NovaLT16"
    elif failure == "QUOTE_NOT_IN_SOURCE":
        item["context"]["quote"] = body.replace("order", "contract")
    elif failure == "SOURCE":
        item["facts"] = [{"field": "product", "value": "NovaLT16", "quote": body}]*2
    else:
        item["entity"]["value"] = None
    source = {"windows": [{"start": 0, "end": len(body), "text": body}]}
    before = deepcopy((item, d, source))
    r = diagnose(json.dumps({"items": [item]}), d, source)
    assert r["accepted_count"] == 0 and r["items"][0]["first_error"] == failure
    assert before == (item, d, source)
    if failure == "SOURCE":
        assert r["items"][0]["duplicate_fields"] == ["product"]
    if failure == "AMBIGUOUS_QUOTE":
        assert len(r["items"][0]["quote_checks"][1]["body_occurrences"]) == 2


def test_unique_context_is_not_permission_to_pick_a_repeated_entity_quote():
    from bct.v4.quote_diagnostics import diagnose
    body = "NovaLT16 appears in a heading.\nForge received new orders for NovaLT16."
    d = doc(body, "Forge", url="https://forge.example/press-release/order")
    a = body.index("Forge")
    context = body[a:]
    item = {"kind": "PHYSICAL_PRODUCT", "role": "DEMAND_INCREASE", "actuality": "ACTUAL",
            "context": {"quote": context}, "entity": {"value": "NovaLT16", "quote": "NovaLT16"}, "facts": []}
    r = diagnose(json.dumps({"items": [item]}), d, {"windows": [{"start": a, "end": len(body), "text": context}]})
    assert r["accepted_count"] == 0 and r["first_error_counts"] == {"AMBIGUOUS_QUOTE": 1}
    q = r["items"][0]["quote_checks"][1]
    assert len(q["transmitted_occurrences"]) == len(q["exact_context_occurrences"]) == 1


@pytest.mark.parametrize("entity", ["NovaLT16", "battery cells", "gas turbines"])
def test_actual_capacity_change_is_kept_as_supply_not_an_order(entity):
    r = reading(f"Forge production capacity for {entity} increased.", entity)
    assert len(r["forwarded_events"]) == 1 and r["counts"]["demand_signals"] == 0
    assert r["counts"]["supply_signals"] == 1
    assert r["forwarded_events"][0]["advisory_role"] == "SUPPLY_INCREASE"
    assert not r["forwarded_events"][0]["qualified"] and not r["candidates"]
