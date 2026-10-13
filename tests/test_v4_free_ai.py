"""Executed failure injection is separate from BLOCKED live API connectivity."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from bct.v4.free_ai import (APIError, HTTPAdapter, MODELS, Router, SCHEMA, annotate,
                            api_status, checked_config, source_input, validate_output)
from bct.v4.store import Ledger
from bct.v4.pipeline import cycle

NOW = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)
ENV = {"GEMINI_API_KEY": "test-gemini-credential", "GROQ_API_KEY": "test-groq-credential"}


def config():
    c = json.loads((Path(__file__).parents[1] / "config/v4-free-ai.json").read_text())
    c["enabled"] = True
    for p in MODELS:
        c["accounts"][p].update(verified_free=True, tier="Free", checked_at=NOW.isoformat(),
                                evidence="SYNTHETIC_FREE_ACCOUNT_FIXTURE", settings_revision="fixture-1",
                                limits={"rpm": 30, "rpd": 1000, "tpm": 100000, "tpd": 200000})
    return c


def document(body="Orders for NovaLT16 production slots are planned for 2028.", id="doc-1"):
    return {"document_id": id, "body": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "origin_url": "https://energy.gov/articles/fixture", "provenance": "PASS",
            "origin_id": "fixture", "origin_publisher": "Fixture", "body_status": "FULL",
            "published_at": "2026-10-12", "publication_precision": "DAY", "acquired_at": NOW.isoformat()}


def response(doc, entity="NovaLT16", kind="PHYSICAL_PRODUCT", actuality="PLAN", **extra):
    start = doc["body"].index(entity)
    item = {"kind": kind, "role": "DEMAND_INCREASE", "actuality": actuality,
            "context": {"quote": doc["body"].split("\n")[0][:1000], "start": 0, "end": len(doc["body"].split("\n")[0][:1000])},
            "entity": {"value": entity, "quote": entity, "start": start, "end": start + len(entity)}, "facts": []}
    item.update(extra)
    return {"text": json.dumps({"items": [item]}), "usage": {"input_tokens": 20, "output_tokens": 40, "total_tokens": 60}, "headers": {}}


class Fake:
    def __init__(self, outputs):
        self.outputs, self.calls = outputs, []
    def call(self, provider, source, max_output):
        self.calls.append(provider)
        result = self.outputs[provider]
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)


def router(ledger, fake, c=None, run="run-1", at=NOW, env=ENV):
    return Router(ledger, c or config(), run_id=run, adapter=fake, env=env, clock=lambda: at)


@pytest.mark.parametrize("kind", ["QUOTA", "TIMEOUT", "SERVER", "NETWORK", "AUTH"])
def test_gemini_failure_falls_once_to_groq_and_skips_rest_of_run(tmp_path, kind):
    doc = document()
    fake = Fake({"gemini": APIError(kind), "groq": response(doc)})
    with_ledger = Ledger(tmp_path)
    r = router(with_ledger, fake)
    assert r.read(doc)["provider"] == "groq"
    other = document(id="doc-2", body=doc["body"] + " Orders increased.")
    assert r.read(other)["provider"] == "groq"
    assert fake.calls == ["gemini", "groq", "groq"]
    assert r.state("gemini")["blocked"]
    with_ledger.close()


def test_both_outages_store_wait_without_completion_or_source_deletion(tmp_path):
    ledger = Ledger(tmp_path)
    doc = document(); ledger.capture(doc)
    fake = Fake({"gemini": APIError("TIMEOUT"), "groq": APIError("SERVER")})
    assert router(ledger, fake).read(doc)["status"] == "WAIT_API"
    assert fake.calls == ["gemini", "groq"]
    assert ledger.latest_documents() == [doc]
    assert ledger.db.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 0
    assert api_status(ledger)["wait_api_documents"] == 1
    ledger.close()


def test_restart_in_fresh_process_preserves_block_and_attempt(tmp_path):
    ledger = Ledger(tmp_path)
    fake = Fake({"gemini": APIError("QUOTA"), "groq": response(document())})
    assert router(ledger, fake).read(document())["provider"] == "groq"
    ledger.close()
    code = "from bct.v4.store import Ledger; from bct.v4.free_ai import Router; import json,sys; l=Ledger(sys.argv[1]); r=Router(l,json.loads(sys.argv[2])); s=r.state('gemini'); print(s['blocked'],s['error_kind'],bool(s['retry_not_before'])); l.close()"
    completed = subprocess.run([sys.executable, "-c", code, str(tmp_path), json.dumps(config())], check=True, capture_output=True, text=True)
    assert completed.stdout.strip() == "True QUOTA True"
    reopened = Ledger(tmp_path)
    r = router(reopened, fake, run="restart", at=NOW + timedelta(minutes=30))
    assert r.read(document(id="other", body=document()["body"] + " More orders."))["provider"] == "groq"
    assert fake.calls == ["gemini", "groq", "groq"]
    reopened.close()


def test_retry_after_daily_unknown_and_account_zero_wait_policies(tmp_path):
    ledger = Ledger(tmp_path)
    r = router(ledger, Fake({}))
    r.block("gemini", APIError("QUOTA", retry_at=NOW + timedelta(minutes=5)))
    assert r.state("gemini")["retry_not_before"] == (NOW + timedelta(minutes=5)).isoformat()
    r.block("gemini", APIError("QUOTA", daily=True))
    assert r.state("gemini")["retry_not_before"] == (NOW + timedelta(hours=24)).isoformat()
    r.block("gemini", APIError("ACCOUNT"))
    r2 = router(ledger, Fake({}), run="next", at=NOW + timedelta(days=1))
    assert r2.available("gemini") == "SETTINGS_CHANGE_REQUIRED"
    ledger.close()


def test_recovery_only_one_probe_then_use_gemini_next_normal_run(tmp_path):
    ledger = Ledger(tmp_path)
    fake = Fake({"gemini": APIError("TIMEOUT"), "groq": response(document())})
    router(ledger, fake).read(document())
    fake.outputs["gemini"] = response(document())
    r = router(ledger, fake, run="recovered", at=NOW + timedelta(hours=2))
    assert r.read(document(id="recovery", body=document()["body"] + " New."))["provider"] == "gemini"
    assert not r.state("gemini")["blocked"]
    assert sum(x.get("recovery_probe", False) for x in r.events("API_ATTEMPT")) == 1
    ledger.close()


def test_dedup_same_input_same_run_restart_and_alias(tmp_path):
    ledger = Ledger(tmp_path); fake = Fake({"gemini": response(document())})
    r = router(ledger, fake)
    assert not r.read(document())["cached"]
    assert r.read(document())["cached"]
    assert router(ledger, fake, run="restart").read(document())["cached"]
    alias = document(id="alias"); alias["origin_url"] = "https://energy.gov/articles/alias"
    item = r.read(alias)["result"]["items"][0]
    assert item["entity"]["reference"]["document_id"] == "alias"
    assert fake.calls == ["gemini"]
    ledger.close()


def test_interrupted_committed_attempt_is_not_resent(tmp_path):
    ledger = Ledger(tmp_path); fake = Fake({"gemini": response(document()), "groq": response(document())})
    r = router(ledger, fake)
    r.read(document())
    # Simulate crash after ATTEMPT in a distinct clean ledger by copying its event only.
    lost = Ledger(tmp_path / "lost")
    with lost.db:
        lost.event("API_ATTEMPT", r.events("API_ATTEMPT")[0])
    lost.close()
    lost = Ledger(tmp_path / "lost")
    result = router(lost, fake, run="restart").read(document())
    assert result["provider"] == "groq" and fake.calls == ["gemini", "groq"]
    lost.close(); ledger.close()


@pytest.mark.parametrize("kind", ["POLICY", "INPUT_INVALID"])
def test_policy_and_bad_input_never_provider_hop(tmp_path, kind):
    ledger = Ledger(tmp_path); fake = Fake({"gemini": APIError(kind), "groq": response(document())})
    assert router(ledger, fake).read(document())["status"] in ("INPUT_ERROR", "REVIEW_REQUIRED")
    assert fake.calls == ["gemini"]
    ledger.close()


@pytest.mark.parametrize("mutation", ["key", "private", "personal", "policy", "query", "hash", "email"])
def test_public_input_safety_preflight_without_any_api(tmp_path, mutation):
    doc = document()
    if mutation == "key": doc = document(body=ENV["GEMINI_API_KEY"])
    if mutation == "email": doc = document(body="Contact jane@example.com regarding production slots.")
    if mutation == "private": doc["confidential"] = True
    if mutation == "personal": doc["personal_data"] = True
    if mutation == "policy": doc["api_transfer_forbidden"] = True
    if mutation == "query": doc["origin_url"] += "?token=private"
    if mutation == "hash": doc["body_sha256"] = "wrong"
    ledger = Ledger(tmp_path); fake = Fake({})
    assert router(ledger, fake).read(doc)["status"] in ("INPUT_ERROR", "REVIEW_REQUIRED")
    assert fake.calls == []
    ledger.close()


def test_free_only_missing_key_paid_unverified_and_stale_account(tmp_path):
    ledger = Ledger(tmp_path); fake = Fake({})
    assert router(ledger, fake, env={}).read(document())["status"] == "WAIT_API"
    for change in ({"tier": "Paid"}, {"verified_free": False}, {"checked_at": "2026-01-01T00:00:00Z"}):
        c = config()
        for p in MODELS: c["accounts"][p].update(change)
        assert router(ledger, fake, c=c).read(document())["status"] == "WAIT_API"
    assert fake.calls == []
    ledger.close()


@pytest.mark.parametrize("mutation", ["third", "model", "order", "timeout", "limit"])
def test_no_unapproved_provider_models_or_unbounded_limits(mutation):
    c = config()
    if mutation == "third": c["providers"].append("xai")
    if mutation == "order": c["providers"].reverse()
    if mutation == "model": c["models"]["groq"] = "other-model"
    if mutation == "timeout": c["timeout_seconds"] = 600
    if mutation == "limit": c["max_calls_per_run"] = 99999
    with pytest.raises(ValueError): checked_config(c)


def test_budget_reserved_before_call_and_persists_restart(tmp_path):
    ledger = Ledger(tmp_path); fake = Fake({"gemini": response(document()), "groq": response(document())})
    c = config(); c["accounts"]["gemini"]["limits"]["rpm"] = 1
    assert router(ledger, fake, c=c).read(document())["provider"] == "gemini"
    r = router(ledger, fake, c=c, run="restart")
    assert r.read(document(id="new", body=document()["body"] + " New."))["provider"] == "groq"
    assert fake.calls == ["gemini", "groq"]
    assert all(x["reserved_tokens"] > 0 for x in r.events("API_ATTEMPT"))
    ledger.close()


@pytest.mark.parametrize("entity,kind", [("Item 7.01.", "DISCLOSURE_HEADING"), ("notes", "GENERAL_EXPRESSION"), ("gas turbines", "PRODUCT_FAMILY"), ("NovaLT16", "PHYSICAL_PRODUCT")])
def test_source_backed_types_unknown_target_and_new_products(entity, kind):
    doc = document(body=entity + " delivery plans for 2028.")
    selected = source_input(doc, config(), ENV)
    result = validate_output(response(doc, entity=entity, kind=kind)["text"], doc, selected)
    item = result["items"][0]
    assert item["physical_exploration_lead"] == (kind in ("PRODUCT_FAMILY", "PHYSICAL_PRODUCT"))
    assert item["s_stage"] == "UNKNOWN" and not item["forecast_candidate"]
    assert item["target"]["supply_pool"] is None


@pytest.mark.parametrize("entity", ["Item 7.01.", "notes", "capacity"])
def test_model_claiming_heading_or_generic_physical_is_rejected(entity):
    doc = document(body=entity + " planned for 2028.")
    with pytest.raises(APIError, match="SOURCE"):
        validate_output(response(doc, entity=entity)["text"], doc, source_input(doc, config(), ENV))


@pytest.mark.parametrize("change", ["invented", "offset", "extra", "duplicate", "truncated", "not_selected"])
def test_json_and_source_validation_falsifications(change):
    doc = document(); raw = json.loads(response(doc)["text"])
    selected = source_input(doc, config(), ENV)
    text = None
    if change == "invented": raw["items"][0]["entity"]["value"] = "OtherModel"
    if change == "offset": raw["items"][0]["entity"]["start"] = 0
    if change == "extra": raw["s3"] = True
    if change == "duplicate": text = '{"items": [], "items": []}'
    if change == "truncated": text = '{"items": ['
    if change == "not_selected": selected["windows"] = []
    with pytest.raises(APIError): validate_output(text or json.dumps(raw), doc, selected)


def test_format_fallback_no_repair_loop_and_restart_cache(tmp_path):
    ledger = Ledger(tmp_path)
    fake = Fake({"gemini": {"text": "bad json", "usage": {}, "headers": {}}, "groq": response(document())})
    r = router(ledger, fake)
    assert r.read(document())["provider"] == "groq"
    assert router(ledger, fake, run="restart").read(document())["cached"]
    assert fake.calls == ["gemini", "groq"]
    ledger.close()


def test_normal_unknown_is_success_and_never_fallback(tmp_path):
    ledger = Ledger(tmp_path)
    fake = Fake({"gemini": {"text": '{"items":[]}', "usage": {"total_tokens": 12}, "headers": {}}})
    result = router(ledger, fake).read(document())
    assert result["status"] == "PASS" and result["result"]["items"] == []
    assert fake.calls == ["gemini"]
    ledger.close()


def test_http_payload_fixed_models_schema_hosts_no_paid_tools_or_retries():
    adapter = HTTPAdapter(ENV); source = source_input(document(), config(), ENV)
    for p in MODELS:
        url, headers, payload = adapter.request(p, source, 2048)
        assert "tools" not in payload and "store" not in payload
        assert ("generativelanguage.googleapis.com" if p == "gemini" else "api.groq.com") in url
        assert MODELS[p] in url or payload["model"] == MODELS[p]
        assert "test-" not in json.dumps(payload)
    assert SCHEMA["additionalProperties"] is False


def test_opt_in_cycle_wait_keeps_collection_and_old_cpu_paths(tmp_path, monkeypatch):
    class Client:
        calls = []
        def document(self, url):
            self.calls.append(url)
            return document(), None, {}
    monkeypatch.setattr("bct.v4.free_ai.os.environ", {})
    client = Client()
    result = cycle(tmp_path, {"urls": [document()["origin_url"]], "document_limit": 1},
                   use_ai=False, client=client, api_config=config(), api_adapter=Fake({}))
    assert result["live_captured"] == 1
    assert result["api_annotations"]["wait_api_documents"] == 1
    assert result["api_calls_this_run"] == 0
    ledger = Ledger(tmp_path)
    assert ledger.status()["documents"] == 1 and ledger.status()["integrity"] == "ok"
    ledger.close()


def test_api_backup_restore_keeps_jobs_blocks_and_dedup(tmp_path):
    ledger = Ledger(tmp_path / "source"); fake = Fake({"gemini": APIError("TIMEOUT"), "groq": response(document())})
    ledger.capture(document()); router(ledger, fake).read(document())
    ledger.backup(tmp_path / "restored/v4.sqlite3"); ledger.close()
    restored = Ledger(tmp_path / "restored")
    assert router(restored, fake, run="restored").read(document())["cached"]
    assert api_status(restored)["provider_states"]["gemini"]["blocked"]
    assert fake.calls == ["gemini", "groq"]
    restored.close()


@pytest.mark.parametrize("code,body,expected", [(429, '{"error":"daily quota exhausted"}', "QUOTA"),
    (429, '{"error":"quota limit: 0"}', "ACCOUNT"), (503, '{}', "SERVER"),
    (429, '{"error":{"details":[{"quotaValue":"0"}]}}', "ACCOUNT"),
    (400, '{"error":"Billing required for free tier access"}', "ACCOUNT"),
    (401, '{}', "AUTH"), (403, '{"error":"organization policy prohibits transfer"}', "POLICY"),
    (400, '{"error":"unsupported input format"}', "INPUT_INVALID")])
def test_actual_http_adapter_error_mapping_one_post_and_no_error_text(code, body, expected):
    adapter = HTTPAdapter(ENV)
    class Opener:
        count = 0
        def open(self, request, timeout):
            self.count += 1
            assert timeout == 60
            raise HTTPError(request.full_url, code, "private-credential-echo", {"Retry-After": "3600"}, BytesIO(body.encode()))
    opener = Opener(); adapter.opener = opener
    with pytest.raises(APIError) as result:
        adapter.call("gemini", source_input(document(), config(), ENV), 2048)
    assert result.value.kind == expected and str(result.value) == expected
    assert opener.count == 1
    if expected == "QUOTA": assert result.value.retry_at is not None


@pytest.mark.parametrize("error,expected", [(TimeoutError("private"), "TIMEOUT"),
    (URLError("network unavailable"), "NETWORK"), (URLError("egress policy blocked"), "POLICY")])
def test_http_timeout_network_and_policy_mapping(error, expected):
    adapter = HTTPAdapter(ENV)
    class Opener:
        count = 0
        def open(self, request, timeout):
            self.count += 1
            raise error
    adapter.opener = Opener()
    with pytest.raises(APIError, match=expected): adapter.call("groq", {}, 2048)
    assert adapter.opener.count == 1


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_http_response_decoding_and_measured_usage(provider):
    text = response(document())["text"]
    if provider == "gemini":
        payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}],
                   "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 40, "totalTokenCount": 60}}
    else:
        payload = {"choices": [{"finish_reason": "stop", "message": {"content": text}}],
                   "usage": {"prompt_tokens": 20, "completion_tokens": 40, "total_tokens": 60}}
    class Response:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, n): return json.dumps(payload).encode()
    class Opener:
        count = 0
        def open(self, req, timeout): self.count += 1; return Response()
    adapter = HTTPAdapter(ENV); adapter.opener = Opener()
    actual = adapter.call(provider, {}, 2048)
    assert actual["text"] == text and actual["usage"]["total_tokens"] == 60
    assert adapter.opener.count == 1


def test_near_remote_quota_stops_provider_for_rest_of_run(tmp_path):
    ledger = Ledger(tmp_path)
    low = response(document()); low["headers"] = {"x-ratelimit-remaining-requests": "10"}
    fake = Fake({"gemini": low, "groq": response(document())})
    r = router(ledger, fake)
    assert r.read(document())["provider"] == "gemini"
    assert r.read(document(id="next", body=document()["body"] + " More."))["provider"] == "groq"
    assert fake.calls == ["gemini", "groq"]
    ledger.close()


def test_input_windows_boundaries_unknown_fields_literal_dates_and_negation():
    doc = document(body="NovaLT16 orders were not signed. Delivery may occur in 2028.\n" + "irrelevant " * 1000)
    c = config(); c["max_input_characters"] = 200
    selected = source_input(doc, c, ENV)
    payload = response(doc, actuality="NEGATED")
    data = json.loads(payload["text"])
    date = doc["body"].index("2028")
    data["items"][0]["facts"] = [{"field": "need_time", "value": "2028", "quote": "2028", "start": date, "end": date + 4}]
    checked = validate_output(json.dumps(data), doc, selected)
    item = checked["items"][0]
    assert item["actuality"] == "NEGATED" and item["facts"][0]["value"] == "2028"
    assert item["target"]["specification"] is None and item["s_stage"] == "UNKNOWN"
    assert selected["selected_characters"] <= 200 and selected["body_characters"] > 1000


def test_json_publication_date_cannot_override_verified_metadata():
    doc = document(); data = json.loads(response(doc)["text"])
    data["items"][0]["facts"] = [{"field": "published_at", "value": "2028", "quote": "2028", "start": 51, "end": 55}]
    with pytest.raises(APIError): validate_output(json.dumps(data), doc, source_input(doc, config(), ENV))


def test_analyze_queue_advances_beyond_completed_documents(tmp_path, monkeypatch):
    c = config(); c["document_limit"] = 1
    for p in MODELS: c["accounts"][p]["checked_at"] = datetime.now(timezone.utc).isoformat()
    docs = [document(id=str(i), body=document()["body"] + " New " + str(i)) for i in range(2)]
    for doc in docs: doc["origin_url"] += "/" + doc["document_id"]
    ledger = Ledger(tmp_path)
    for doc in docs: ledger.capture(doc)
    ledger.close()
    fake = Fake({"gemini": response(docs[0])})
    monkeypatch.setattr("bct.v4.free_ai.HTTPAdapter.call", fake.call)
    monkeypatch.setattr("bct.v4.free_ai.os.environ", ENV)
    assert annotate(tmp_path, c)["results"][0]["document_id"] == "0"
    fake.outputs["gemini"] = response(docs[1])
    assert annotate(tmp_path, c)["results"][0]["document_id"] == "1"
    assert fake.calls == ["gemini", "gemini"]


def test_real_connectivity_is_blocked_without_keys_not_fake_pass(tmp_path):
    ledger = Ledger(tmp_path); ledger.capture(document()); ledger.close()
    c = config()
    for provider in MODELS:
        fake = Fake({})
        ledger = Ledger(tmp_path)
        result = router(ledger, fake, env={}).read(document(), probe_provider=provider)
        assert result["status"] == "WAIT_API" and fake.calls == []
        ledger.close()


def test_classification_context_must_match_source_and_contain_entity():
    doc = document(); data = json.loads(response(doc)["text"])
    data["items"][0]["context"] = {"quote": "Orders", "start": 0, "end": 6}
    with pytest.raises(APIError, match="SOURCE"):
        validate_output(json.dumps(data), doc, source_input(doc, config(), ENV))


def test_unsupported_request_contract_not_repeated_on_next_doc_or_restart(tmp_path):
    ledger = Ledger(tmp_path); fake = Fake({"gemini": APIError("INPUT_INVALID")})
    r = router(ledger, fake)
    assert r.read(document())["status"] == "INPUT_ERROR"
    other = document(id="other", body=document()["body"] + " New input.")
    assert r.read(other)["reason"] == "LOCAL_REQUEST_CONTRACT_FIX_REQUIRED"
    ledger.close(); ledger = Ledger(tmp_path)
    assert router(ledger, fake, run="restart").read(other)["status"] == "INPUT_ERROR"
    assert fake.calls == ["gemini"]
    ledger.close()
