"""SYNTHETIC safety/typed integration; not independent accuracy or EARLY gain."""
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

import pytest

from bct import future_body, precursor_collection as collection
from bct.v4.public_input import review_native, selected_input, valid_article_url
from bct.v4.research_adapter import analyze, save
from bct.v4.free_ai import source_input, APIError
from bct.v4.store import Ledger
from test_v4_free_ai import config, document
from test_precursor_evidence_graph import pair, ASOF


def native(text, footer=""):
    raw = ('<html><head><meta property="article:published_time" content="2026-10-01" /></head>'
           '<body><article><h1>Aehr Test Systems public release</h1><p>' + text + '</p>'
           + footer + '</article></body></html>').encode()
    body = future_body.extract_document(raw.decode())["body"]
    d = document(body)
    d.update(origin_url="https://www.aehr.com/2026/10/public-release/", published_at="2026-10-01",
             raw_sha256=hashlib.sha256(raw).hexdigest(), checks={"http_success": True, "not_republication": True})
    r = {"url": d["origin_url"], "published_at": d["published_at"],
         "raw_sha256": d["raw_sha256"], "body_sha256": d["body_sha256"]}
    return d, raw, r


def test_public_contact_footer_is_not_sent_and_original_is_preserved():
    d, raw, r = native("Aehr signed new orders for FOX-XP equipment. Delivery is required in 2028.",
                       '<p>General information on the supplier and this public release. ' + 'Public information. '*22 + '</p>'
                       '<p>Contacts:</p><p>Media Office (510) 623-9400 media@example.com</p>')
    original = deepcopy(d)
    review = review_native(d, raw, r)
    assert review["status"] == "PASS", review
    selected = source_input({**d, "api_safe_input_review": review}, config(), {})
    assert selected["windows"] and "media@example.com" not in json.dumps(selected)
    assert review["excluded_ranges"] and d == original
    for w in selected["windows"]:
        assert d["body"][w["start"]:w["end"]] == w["text"]


@pytest.mark.parametrize("danger", ["authorization: Bearer private-token", "password=private", "account number 12345678",
                                     "gsk_privatevalue123", "api_key=secret"])
def test_credentials_outside_selected_window_still_block(danger):
    d, raw, r = native("Signed new orders for turbines. " + danger)
    assert "SENSITIVE_DATA_ANYWHERE_IN_BODY" in review_native(d, raw, r)["reasons"]


@pytest.mark.parametrize("flag", ["confidential", "personal_data", "api_transfer_forbidden"])
def test_explicit_restrictions_cannot_be_cleared_by_review(flag):
    d, raw, r = native("Signed new orders for turbines.")
    review = review_native(d, raw, r)
    d[flag] = True
    assert "EXPLICIT_TRANSFER_RESTRICTION" in review_native(d, raw, r)["reasons"]
    with pytest.raises(APIError):
        source_input({**d, "api_safe_input_review": review}, config(), {})


def test_unlabelled_body_contact_missing_native_or_tampered_source_block():
    d, raw, r = native("Signed new orders for turbines; ask person@example.com for customer information.")
    assert "CONTACT_OUTSIDE_VERIFIED_TERMINAL_FOOTER" in review_native(d, raw, r)["reasons"]
    assert "NATIVE_ORIGINAL_MISSING" in review_native(d, None, r)["reasons"]
    assert "NATIVE_HASH_MISMATCH" in review_native(d, raw+b"changed", r)["reasons"]
    wrong = {**r, "published_at": "2026-09-30"}
    assert "NATIVE_PUBLICATION_UNVERIFIED" in review_native(d, raw, wrong)["reasons"]


@pytest.mark.parametrize("url,expected", [
    ("https://www.eia.gov/todayinenergy/detail.php?id=68064", True),
    ("https://www.eia.gov/todayinenergy/detail.php?id=68064&token=private", False),
    ("https://www.eia.gov/todayinenergy/detail.php?id=68064&id=68084", False),
    ("https://www.eia.gov/todayinenergy/detail.php?unknown=68064", False),
    ("https://www.eia.gov/todayinenergy/detail.php?id=%36%38%30%36%34", False),
    ("https://www.eia.gov/todayinenergy/detail.php?id=123456789", False),
    ("https://www.eia.gov/private.php?id=68064", False),
    ("https://other.example/todayinenergy/detail.php?id=68064", False),
    ("https://127.0.0.1/todayinenergy/detail.php?id=68064", False),
])
def test_only_narrow_official_article_identifier_is_accepted(url, expected):
    assert valid_article_url(url) is expected
    assert not valid_article_url(url, "https://other.example/replaced")


def test_negation_and_counterevidence_are_not_cut_to_fit_budget():
    d, raw, r = native("Signed new orders for turbines.")
    # Full paragraphs are deliberately over budget when linked by a caveat.
    d["body"] += "\nHowever, production was not expanded; " + "qualification is incomplete. "*25
    d["body_sha256"] = hashlib.sha256(d["body"].encode()).hexdigest()
    review = {**review_native(*native("Signed new orders for turbines.")), "body_sha256": d["body_sha256"]}
    c = config(); c.update(max_input_characters=600)
    with pytest.raises(ValueError, match="NO_COMPLETE_SAFE_SIGNAL"):
        selected_input(d, c, review, {})


def proposal(d, role, *, facts=None):
    # Whole original paragraph, source addresses computed by Python on replay.
    text = collection.structure(d)["retained_collection_events"][0]["source_quote"]
    item = {"kind": "PHYSICAL_PRODUCT", "role": role, "actuality": "ACTUAL",
            "context": {"quote": text}, "entity": {"value": "tungsten", "quote": text},
            "facts": [{"field": k, "value": v, "quote": text} for k, v in (facts or {}).items()]}
    return {"text": json.dumps({"items": [item]}),
            "source": {"windows": [{"start": 0, "end": len(d["body"]), "text": d["body"]}]}}


def test_adapter_reaches_actual_engine_and_preserves_advisory_and_source(tmp_path):
    docs = list(pair())
    docs[1]["body"] = docs[1]["body"].replace("is under construction", "production delayed and is under construction")
    docs[1]["body_sha256"] = hashlib.sha256(docs[1]["body"].encode()).hexdigest()
    proposals = {docs[0]["document_id"]: proposal(docs[0], "DEMAND_INCREASE"),
                 docs[1]["document_id"]: proposal(docs[1], "SUPPLY_DELAY")}
    before = deepcopy((docs, proposals))
    off = analyze(docs, proposals, enabled=False, mode="SYNTHETIC", as_of=ASOF)
    on = analyze(docs, proposals, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert (docs, proposals) == before
    assert on["forwarded_events"], on["held"]
    forwarded_ids = {e["event_id"] for e in on["forwarded_events"]}
    assert any(e["event_id"] in forwarded_ids for t in on["engine"]["targets"] for e in t["events"])
    assert on["candidates"] and not off["forwarded_events"]
    assert all(c["s_stage"] == "UNKNOWN" and c["research_only"] for c in on["candidates"])
    ledger = Ledger(tmp_path / "live")
    result = save(ledger, docs, proposals, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert save(ledger, docs, proposals, enabled=True, mode="SYNTHETIC", as_of=ASOF) == result
    backup = tmp_path / "restored" / "v4.sqlite3"; ledger.backup(backup)
    n = ledger.status(); ledger.close()
    code = 'import sys,json; from bct.v4.store import Ledger; l=Ledger(sys.argv[1]); print(json.dumps(l.status())); l.close()'
    restored = json.loads(subprocess.run([sys.executable, "-c", code, str(backup.parent)], check=True, capture_output=True, text=True).stdout)
    assert restored == n
    reopened = Ledger(backup.parent)
    assert save(reopened, docs, proposals, enabled=True, mode="SYNTHETIC", as_of=ASOF) == result
    assert reopened.status() == n
    reopened.close()


@pytest.mark.parametrize("change", ["specification", "region", "customer", "future", "republication", "negation", "relief", "money"])
def test_adapter_does_not_promote_counterexamples(change):
    docs = list(pair())
    if change == "specification":
        docs[1]["body"] = docs[1]["body"].replace("military-grade", "non-Chinese")
    elif change == "region":
        docs[1]["body"] += " The military-grade tungsten is for military drones in Germany under contract K-242."
    elif change == "customer":
        docs[1]["body"] += " The military-grade tungsten is for industrial buyers in United States under contract K-242."
    elif change == "future":
        docs[1]["published_at"] = "2027-01-01T00:00:00+00:00"
    elif change == "republication":
        docs[1]["origin_publisher"] = docs[0]["origin_publisher"]
    elif change == "negation":
        docs[0]["body"] = docs[0]["body"].replace("signed firm new orders", "did not sign firm new orders")
    elif change == "relief":
        docs[1]["body"] += " Qualified inventory of military-grade tungsten covers all contracted demand."
    elif change == "money":
        docs[0]["body"] = docs[0]["body"].replace("signed firm new orders", "received a government grant of $800 million")
    for d in docs:
        d["body_sha256"] = hashlib.sha256(d["body"].encode()).hexdigest()
    p = {docs[0]["document_id"]: proposal(docs[0], "DEMAND_INCREASE")}
    result = analyze(docs, p, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert not result["candidates"], (change, result["engine"]["pairs"])


def test_research_adapter_cannot_be_live():
    with pytest.raises(ValueError, match="CANNOT_BE_LIVE"):
        analyze(list(pair()), {}, enabled=True, mode="LIVE")


def test_ai_only_region_fact_changes_actual_downstream_candidate():
    docs = list(pair())
    docs[0]["body"] = docs[0]["body"].split(";")[0].replace(" in United States", "") + "; United States delivery of tungsten required in 2028."
    docs[0]["body_sha256"] = hashlib.sha256(docs[0]["body"].encode()).hexdigest()
    docs[0] = collection.structure(docs[0])
    assert "region" not in docs[0]["precursor_events"][0]["scope"]
    proposals = {docs[0]["document_id"]: proposal(docs[0], "DEMAND_INCREASE", facts={"region": "United States"})}
    # The product appears twice; use an exact, uniquely located entity quote.
    raw = json.loads(proposals[docs[0]["document_id"]]["text"])
    raw["items"][0]["entity"]["quote"] = "military-grade tungsten"
    proposals[docs[0]["document_id"]]["text"] = json.dumps(raw)
    off = analyze(docs, proposals, mode="SYNTHETIC", as_of=ASOF)
    on = analyze(docs, proposals, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert not off["candidates"] and len(on["candidates"]) == 1
    assert any(e.get("adapter_origin") and e["scope"]["region"] == "united states"
               for t in on["engine"]["targets"] for e in t["events"])


def test_supply_decrease_keeps_residual_demand_and_unknown_total_supply():
    docs = list(pair())
    docs[0]["body"] = docs[0]["body"].replace("signed firm new orders", "confirmed residual orders")
    docs[1]["body"] = docs[1]["body"].replace("is under construction", "fell and is under construction")
    for d in docs:
        d["body_sha256"] = hashlib.sha256(d["body"].encode()).hexdigest()
    p = {docs[1]["document_id"]: proposal(docs[1], "SUPPLY_DECREASE")}
    r = analyze(docs, p, enabled=True, mode="SYNTHETIC", as_of=ASOF)
    assert r["supply_decrease_reviews"], r["held"]
    assert r["supply_decrease_reviews"][0]["residual_demand"]["incremental"] is False
    assert r["supply_decrease_reviews"][0]["total_qualified_supply"] == "UNKNOWN"
    assert not r["candidates"]


def gold_fixture():
    d = document("NovaLT16 production capacity increased. Delivery required in 2028.")
    ref = {"start": 0, "end": len(d["body"]), "quote": d["body"]}
    facts = [{"field": "product", "status": "VERIFIED_PRESENT", "value": "NovaLT16", "reference": ref, "reason": "Physical model explicitly named"},
             {"field": "role", "status": "VERIFIED_PRESENT", "value": "SUPPLY_INCREASE", "reference": ref, "reason": "Capacity increased"},
             {"field": "quantity", "status": "VERIFIED_ABSENT", "value": None, "reference": None, "reason": "No physical count in full reviewed input"}]
    g = {"document_id": d["document_id"], "body_sha256": d["body_sha256"], "review_complete": True,
         "reviewed_ranges": [{"start": 0, "end": len(d["body"])}], "targets": [{"entity": "NovaLT16", "events": [{"event_id": "one", "reference": ref, "facts": facts}]}]}
    item = {"kind": "PHYSICAL_PRODUCT", "role": "SUPPLY_INCREASE", "actuality": "UNKNOWN",
            "context": ref, "entity": {"value": "NovaLT16"}, "facts": []}
    return d, g, item, [ref]


def test_event_evaluator_counts_real_denominators_and_ignores_duplicates():
    from bct.v4.event_evaluation import assess
    d, g, item, w = gold_fixture()
    r = assess([item, item], g, d, w)
    assert (r["metrics"]["TP"], r["metrics"]["FP"], r["metrics"]["FN"]) == (2, 0, 0)
    assert r["duplicate_predictions"] == 2 and r["metrics"]["recall_denominator"] == 2
    item["role"] = "SUPPLY_DELAY"
    r = assess([item], g, d, w)
    assert (r["metrics"]["TP"], r["metrics"]["FP"], r["metrics"]["FN"]) == (1, 1, 1)
    assert r["metrics"]["precision"] == r["metrics"]["recall"] == .5


def test_event_evaluator_separates_unreviewed_truth_and_missed_truth():
    from bct.v4.event_evaluation import assess
    d, g, item, w = gold_fixture()
    r = assess([], g, d, w)
    assert r["metrics"]["precision"] is None and r["metrics"]["FN"] == 2
    assert r["metrics"]["truth_absent_unknown"] == 1
    g["review_complete"] = False
    assert assess([item], g, d, w)["status"] == "BLOCKED_TRUTH_UNREVIEWED"


def test_gold_cannot_use_fabricated_quotes_or_absent_values():
    from bct.v4.event_evaluation import check_gold
    d, g, item, w = gold_fixture()
    g["targets"][0]["events"][0]["facts"][0]["reference"] = {"start": 0, "end": 1, "quote": "invented"}
    with pytest.raises(ValueError, match="REFERENCE_MISMATCH"):
        check_gold(g, d, w)


def test_cpu_frozen_windows_are_used_exactly_without_hidden_context(tmp_path):
    from bct.v4.adapters import CPUExtractor
    d = document("Unread context.\nNovaLT16 production capacity increased.")
    a = d["body"].index("NovaLT16")
    w = {"start": a, "end": len(d["body"]), "text": d["body"][a:]}
    calls = []
    class Model:
        def extract_entities(self, text, labels, **kwargs):
            calls.append(text)
            return {"entities": {"product": [{"text": "NovaLT16", "start": 0, "end": 8}]}}
    e = CPUExtractor(tmp_path); e.model = Model(); e.revision = "fixture"
    r = e.extract_windows(d, [w])
    assert calls == [w["text"]] and r["spans"][0]["locator"]["start"] == a
    with pytest.raises(ValueError, match="FROZEN_WINDOW"):
        e.extract_windows(d, [{**w, "text": "altered"}])
