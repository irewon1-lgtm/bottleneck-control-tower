"""Offline checks for truthful RSS AI execution and persistence receipts."""
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def outcome_module():
    spec = importlib.util.spec_from_file_location(
        "rss_ai_outcome", ROOT / ".github/scripts/rss_ai_outcome.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def environment(**changes):
    return {"AI_RESTORE_OUTCOME": "success", "AI_CONFIG_OUTCOME": "success",
            "AI_ENABLED": "true", "AI_ANNOTATION_OUTCOME": "success",
            "AI_SAVE_OUTCOME": "success", "AI_PROCESSED": "3",
            "AI_SUCCESS": "3", "AI_ERROR": "0", "GITHUB_RUN_ID": "offline-1",
            **changes}


@pytest.mark.parametrize(("changes", "status", "saved"), [
    ({}, "ANALYSIS_PASS", 3),
    ({"AI_ENABLED": "false", "AI_ANNOTATION_OUTCOME": "skipped",
      "AI_SAVE_OUTCOME": "skipped", "AI_PROCESSED": "", "AI_SUCCESS": "",
      "AI_ERROR": ""}, "SKIPPED_CONFIG", 0),
    ({"AI_PROCESSED": "0", "AI_SUCCESS": "0", "AI_SAVE_OUTCOME": "skipped"},
     "NO_NEW_INPUT", 0),
    ({"AI_ANNOTATION_OUTCOME": "failure", "AI_SAVE_OUTCOME": "skipped"},
     "FAIL_RUNTIME", 0),
    ({"AI_SAVE_OUTCOME": "failure"}, "FAIL_SAVE", 0),
    ({"AI_SAVE_OUTCOME": "skipped"}, "FAIL_SAVE", 0),
    ({"AI_SUCCESS": "2", "AI_ERROR": "1"}, "FAIL_RUNTIME", 3),
    ({"AI_SUCCESS": "0", "AI_ERROR": "3"}, "FAIL_RUNTIME", 3),
    ({"AI_RESTORE_OUTCOME": "failure", "AI_ENABLED": "false"}, "FAIL_RUNTIME", 0),
    ({"AI_PROCESSED": "", "AI_SUCCESS": "", "AI_ERROR": ""}, "FAIL_RUNTIME", 0),
    ({"AI_PROCESSED": "3", "AI_SUCCESS": "1", "AI_ERROR": "0"}, "FAIL_RUNTIME", 0),
])
def test_receipt_requires_actual_analysis_and_save(changes, status, saved):
    receipt = outcome_module().classify(environment(**changes))
    assert receipt["status"] == status
    assert receipt["persisted"] == saved
    assert receipt["run_id"] == "offline-1"


def test_report_writes_safe_evidence_and_fails_after_persisted_article_errors(tmp_path):
    module = outcome_module()
    output, summary = tmp_path / "outcome.json", tmp_path / "summary"
    env = environment(AI_SUCCESS="2", AI_ERROR="1", GITHUB_STEP_SUMMARY=str(summary),
                      OPENAI_API_KEY="never-copy-secret", AI_PROVIDER_ERROR="private text")
    assert module.report(env, output) == 1
    receipt = json.loads(output.read_text())
    assert receipt["status"] == "FAIL_RUNTIME" and receipt["persisted"] == 3
    assert "FAIL_RUNTIME" in summary.read_text()
    assert "never-copy-secret" not in output.read_text() + summary.read_text()
    assert "private text" not in output.read_text() + summary.read_text()


@pytest.mark.parametrize("changes", [{}, {"AI_ENABLED": "false"},
    {"AI_PROCESSED": "0", "AI_SUCCESS": "0", "AI_SAVE_OUTCOME": "skipped"}])
def test_nonfailure_reports_do_not_turn_skip_or_no_input_into_analysis(tmp_path, changes):
    module = outcome_module()
    output = tmp_path / "outcome.json"
    assert module.report(environment(**changes), output) == 0
    assert json.loads(output.read_text())["status"] in {
        "ANALYSIS_PASS", "SKIPPED_CONFIG", "NO_NEW_INPUT"}
