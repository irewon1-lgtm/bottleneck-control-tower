"""Permit a queue snapshot after *recorded* partial CPU reader failure, not after a broken Gate.

This never approves failed AI readings or S-stage decisions. It only checks
whether prior successful document-level CAS writes and explicit failure records
were saved and the source/version preservation invariants remained intact.
The GitHub job still fails because the native reader step did fail.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path


def verify(report, *, outcome, run_id):
    if outcome not in ("success", "failure"):
        raise ValueError("READER_OUTCOME_UNKNOWN_OR_SKIPPED")
    if outcome == "success":
        return {"status": "READER_PASS_QUEUE_SNAPSHOT_ALLOWED", "reader_outcome": "success"}
    if not isinstance(report, dict) or report.get("run_id") != run_id:
        raise ValueError("READER_PARTIAL_REPORT_NOT_BOUND_TO_CURRENT_RUN")
    proof = report.get("release_proof") or {}
    if not isinstance(proof, dict) or proof.get("status") != "PASS":
        raise ValueError("READER_PARTIAL_RELEASE_PROOF_NOT_PASS")
    required = (
        report.get("state") == "FINISHED"
        and report.get("summary_saved") is True
        and report.get("source_records_unchanged") is True
        and report.get("duplicate_auto_reviews") == 0
        and not report.get("held_prior_version_states")
        and report.get("historical_judgment_holds") == 0
        and report.get("historical_judgment_state") == "PASS"
        and report.get("paid_fallback_calls") == 0
        and report.get("source_eligibility") == "EXACT_FULL_PROVENANCE_OR_VERIFIED_RECOVERED_SOURCE"
    )
    if not required:
        raise ValueError("READER_PARTIAL_SOURCE_OR_HISTORY_GUARD_FAILED")
    results = report.get("results")
    counts = report.get("counts")
    if not isinstance(results, list) or not isinstance(counts, dict):
        raise ValueError("READER_PARTIAL_RESULTS_MISSING")
    if any(not isinstance(x, dict) or x.get("state") not in ("SUCCESS", "ERROR")
           or not x.get("document_id") or not x.get("body_sha256") for x in results):
        raise ValueError("READER_PARTIAL_RESULT_INVALID")
    actual = dict(Counter(x["state"] for x in results))
    if (actual != counts or actual.get("SUCCESS", 0) < 1 or actual.get("ERROR", 0) < 1
            or report.get("attempted") != len(results)
            or report.get("completed_delta") != actual["SUCCESS"]
            or len({(x["document_id"], x["body_sha256"]) for x in results}) != len(results)):
        raise ValueError("READER_PARTIAL_RESULT_LEDGER_MISMATCH")
    calls = report.get("model_calls")
    receipts = report.get("actual_returned_native_calls")
    if (type(calls) is not int or type(receipts) is not int or calls < 1
            or calls != receipts or calls > len(results)):
        raise ValueError("READER_PARTIAL_NATIVE_RECEIPTS_INCOMPLETE")
    return {"status": "PARTIAL_READER_ERRORS_RETAINED_QUEUE_SNAPSHOT_ALLOWED",
            "reader_outcome": "failure", "saved_successes": actual["SUCCESS"],
            "recorded_errors": actual["ERROR"], "overall_run_pass": False}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--outcome", required=True, choices=["success", "failure"])
    args = p.parse_args(argv)
    # Even a successful native step must not accept stale output when one is supplied.
    raw = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else None
    result = verify(raw, outcome=args.outcome, run_id=os.environ["GITHUB_RUN_ID"])
    print("BCT_CPU_READER_PUBLICATION_GATE=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
