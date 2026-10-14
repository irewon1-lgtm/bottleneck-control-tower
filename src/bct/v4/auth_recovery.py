"""Explicit one-shot recovery after externally observed auth, without key changes.

The frozen reader stays unchanged. Historical failures remain append-only, and
only a never-attempted input may consume the operator's recovery evidence.
"""
from datetime import timedelta

from .free_ai import QUOTE_SCHEMA, SYSTEM, VERSION, Router, instant, source_input
from .store import sha


class AuthRecoveryRouter(Router):
    def available(self, provider):
        reason = super().available(provider)
        if (reason == "SETTINGS_CHANGE_REQUIRED" and provider == "groq"
                and getattr(self, "_external_auth_probe", False)):
            return None
        return reason

    def read_unattempted(self, doc, *, auth_evidence=None):
        reviewed = self.reviewed_document(doc)
        source = source_input(reviewed, self.config, self.env)
        key = sha([VERSION, SYSTEM, QUOTE_SCHEMA, source, doc["body_sha256"]])
        if any(x["provider"] == "groq" and x["input_key"] == key
               for x in self.events("API_ATTEMPT")):
            raise ValueError("PREVIOUSLY_ATTEMPTED_INPUT_NO_RETRY")
        if self.config["providers"] != ["groq"] or self.config["max_calls_per_run"] != 1:
            raise ValueError("ONE_GROQ_CALL_REQUIRED")
        state = self.state("groq")
        if auth_evidence is not None:
            self._authorize(auth_evidence, state, key)
        elif state and state.get("blocked"):
            raise ValueError("PROVIDER_STILL_BLOCKED")
        self._external_auth_probe = auth_evidence is not None
        try:
            return self.read(doc)
        finally:
            self._external_auth_probe = False

    def _authorize(self, evidence, state, input_key):
        if (not state or not state.get("blocked") or state.get("error_kind") != "AUTH"
                or not state.get("requires_settings_change")):
            raise ValueError("AUTH_BLOCK_REQUIRED")
        observed = instant(evidence["at_utc"])
        if not (instant(state["at"]) < observed <= self.clock()
                and self.clock() - observed <= timedelta(hours=1)):
            raise ValueError("FRESH_AUTH_EVIDENCE_REQUIRED")
        if (evidence.get("method") != "GET"
                or evidence.get("endpoint") != "https://api.groq.com/openai/v1/models"
                or evidence.get("http_status") != 200
                or evidence.get("model_list_received") is not True
                or evidence.get("configured_model_listed") is not True
                or evidence.get("requests") != 1
                or evidence.get("settings_changed") is not False
                or evidence.get("user_authorized_fresh_generation_probe") is not True):
            raise ValueError("CONFIRMED_AUTH_EVIDENCE_REQUIRED")
        evidence_id = sha(evidence)
        if any(x["evidence_id"] == evidence_id for x in self.events("API_AUTH_RECOVERY_PROBE")):
            raise ValueError("AUTH_EVIDENCE_ALREADY_CONSUMED")
        if super().available("groq") != "SETTINGS_CHANGE_REQUIRED":
            raise ValueError("OTHER_PROVIDER_GUARD_BLOCKS_RECOVERY")
        # Consume before attempting HTTP: interruption cannot grant a second probe.
        self.record("API_AUTH_RECOVERY_PROBE", {
            "provider": "groq", "evidence_id": evidence_id, "evidence": evidence,
            "blocked_state_at": state["at"], "only_input_key": input_key,
            "settings_changed": False, "original_AUTH_block_retained_until_HTTP_success": True})
