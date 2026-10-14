"""Offline failure injection; no credential or HTTP dependency."""
from datetime import timedelta

import pytest

from bct.v4.auth_recovery import AuthRecoveryRouter
from bct.v4.free_ai import APIError, Router
from bct.v4.store import Ledger
from test_v4_free_ai import ENV, NOW, Fake, config, document, response


def evidence(**changes):
    return {"at_utc": (NOW + timedelta(minutes=1)).isoformat(), "method": "GET",
            "endpoint": "https://api.groq.com/openai/v1/models", "http_status": 200,
            "model_list_received": True, "configured_model_listed": True, "requests": 1,
            "settings_changed": False, "user_authorized_fresh_generation_probe": True, **changes}


def setup(tmp_path, output=None, at=None):
    ledger = Ledger(tmp_path)
    cfg = config(); cfg["max_calls_per_run"] = 1
    original = Router(ledger, cfg, env=ENV, clock=lambda: NOW)
    original.block("groq", APIError("AUTH"))
    fake = Fake({"groq": output or response(document())})
    router = AuthRecoveryRouter(ledger, cfg, env=ENV, adapter=fake,
                               clock=lambda: at or NOW + timedelta(minutes=2))
    return ledger, router, fake


def test_current_auth_allows_only_one_fresh_generation_and_keeps_history(tmp_path):
    ledger, router, fake = setup(tmp_path)
    assert router.available("groq") == "SETTINGS_CHANGE_REQUIRED"
    original_config = router.config.copy()
    result = router.read_unattempted(document(), auth_evidence=evidence())
    assert result["status"] == "PASS" and fake.calls == ["groq"]
    assert router.events("API_ATTEMPT")[-1]["recovery_probe"]
    states = router.events("API_PROVIDER_STATE")
    assert states[0]["error_kind"] == "AUTH" and states[0]["blocked"]
    assert not states[-1]["blocked"]
    assert router.config == original_config
    with pytest.raises(ValueError, match="PREVIOUSLY_ATTEMPTED"):
        router.read_unattempted(document())
    ledger.close()


@pytest.mark.parametrize("change", [
    {"http_status": 401}, {"method": "POST"}, {"endpoint": "https://example.com"},
    {"settings_changed": True}, {"user_authorized_fresh_generation_probe": False},
    {"model_list_received": False}, {"configured_model_listed": False}, {"requests": 2},
    {"at_utc": NOW.isoformat()}, {"at_utc": (NOW + timedelta(hours=2)).isoformat()}])
def test_unconfirmed_stale_or_wrong_route_evidence_never_calls(tmp_path, change):
    ledger, router, fake = setup(tmp_path)
    with pytest.raises(ValueError):
        router.read_unattempted(document(), auth_evidence=evidence(**change))
    assert fake.calls == [] and router.state("groq")["blocked"]
    ledger.close()


def test_expired_evidence_does_not_open_block(tmp_path):
    ledger, router, fake = setup(tmp_path, at=NOW + timedelta(hours=2))
    with pytest.raises(ValueError, match="FRESH_AUTH"):
        router.read_unattempted(document(), auth_evidence=evidence())
    assert fake.calls == []
    ledger.close()


def test_actual_failed_input_and_alias_never_retried(tmp_path):
    ledger, router, fake = setup(tmp_path)
    original = Router(ledger, router.config, env=ENV, adapter=Fake({"groq": APIError("AUTH")}), clock=lambda: NOW)
    # Prior failed attempt already exists; append only its real-shaped event.
    from bct.v4.free_ai import QUOTE_SCHEMA, SYSTEM, VERSION, source_input
    from bct.v4.store import sha
    doc = document()
    key = sha([VERSION, SYSTEM, QUOTE_SCHEMA, source_input(doc, router.config, ENV), doc["body_sha256"]])
    original.record("API_ATTEMPT", {"provider": "groq", "input_key": key, "attempt_id": "prior-failed"})
    for alias in (doc, document(id="different-url-same-input")):
        with pytest.raises(ValueError, match="PREVIOUSLY_ATTEMPTED"):
            router.read_unattempted(alias, auth_evidence=evidence())
    assert fake.calls == []
    ledger.close()


def test_failed_recovery_stops_and_cannot_reuse_evidence_after_restart(tmp_path):
    ledger, router, fake = setup(tmp_path, APIError("AUTH"))
    assert router.read_unattempted(document(), auth_evidence=evidence())["status"] == "WAIT_API"
    next_doc = document(id="new", body=document()["body"] + " More orders.")
    restarted = AuthRecoveryRouter(ledger, router.config, env=ENV, adapter=fake,
                                  clock=lambda: NOW + timedelta(minutes=3))
    with pytest.raises(ValueError, match="PROVIDER_STILL_BLOCKED"):
        restarted.read_unattempted(next_doc)
    with pytest.raises(ValueError):
        restarted.read_unattempted(next_doc, auth_evidence=evidence())
    assert fake.calls == ["groq"]
    ledger.close()


def test_crash_after_evidence_consumption_cannot_create_second_probe(tmp_path):
    ledger, router, fake = setup(tmp_path)
    router._authorize(evidence(), router.state("groq"), "would-be-input")
    ledger.close()
    reopened = Ledger(tmp_path)
    restarted = AuthRecoveryRouter(reopened, router.config, env=ENV, adapter=fake,
                                  clock=lambda: NOW + timedelta(minutes=2))
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        restarted.read_unattempted(document(), auth_evidence=evidence())
    assert fake.calls == []
    reopened.close()


def test_empty_valid_generation_is_not_candidate_or_proof_of_accuracy(tmp_path):
    output = {"text": '{"items":[]}', "usage": {"total_tokens": 60}, "headers": {}}
    # A valid HTTP generation with no extracted items is not extraction accuracy.
    ledger, router, fake = setup(tmp_path, output)
    result = router.read_unattempted(document(), auth_evidence=evidence())
    assert result["status"] == "PASS" and result["result"]["items"] == []
    assert result["forecast_candidate"] is False
    assert router.events("API_RECEIVED")[-1]["text"] == output["text"]
    ledger.close()


def test_missing_free_verification_cannot_be_bypassed(tmp_path):
    ledger, router, fake = setup(tmp_path)
    router.config["accounts"]["groq"]["verified_free"] = False
    with pytest.raises(ValueError, match="OTHER_PROVIDER_GUARD"):
        router.read_unattempted(document(), auth_evidence=evidence())
    assert fake.calls == []
    ledger.close()
