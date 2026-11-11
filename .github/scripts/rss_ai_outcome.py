"""Report RSS AI work separately from the GitHub Actions job conclusion."""
import argparse
import json
import os
from pathlib import Path


def classify(env):
    receipt = {"schema_version": 1, "run_id": env.get("GITHUB_RUN_ID", ""),
               "code_sha": env.get("GITHUB_SHA", ""),
               "status": "FAIL_RUNTIME", "reason": "DATABASE_RESTORE_FAILED",
               "processed": 0, "success": 0, "error": 0, "persisted": 0,
               "persisted_success": 0}
    if env.get("AI_RESTORE_OUTCOME") != "success":
        return receipt
    if env.get("AI_CONFIG_OUTCOME") != "success":
        receipt["reason"] = "CONFIGURATION_CHECK_FAILED"
        return receipt
    if env.get("AI_ENABLED") == "false":
        receipt.update(status="SKIPPED_CONFIG", reason="OPENAI_API_KEY_NOT_CONFIGURED")
        return receipt
    if env.get("AI_ENABLED") != "true":
        receipt["reason"] = "CONFIGURATION_RESULT_MISSING"
        return receipt
    if env.get("AI_ANNOTATION_OUTCOME") != "success":
        receipt["reason"] = "ANNOTATION_BATCH_FAILED"
        return receipt
    try:
        counts = {key.lower(): int(env["AI_" + key])
                  for key in ("PROCESSED", "SUCCESS", "ERROR")}
        if any(value < 0 for value in counts.values()) or (
                counts["processed"] != counts["success"] + counts["error"]):
            raise ValueError("invalid counters")
    except (KeyError, TypeError, ValueError):
        receipt["reason"] = "ANNOTATION_COUNTS_INVALID"
        return receipt
    receipt.update(counts)
    if not counts["processed"]:
        receipt.update(status="NO_NEW_INPUT", reason="NO_UNPROCESSED_SIGNAL_ARTICLES")
    elif env.get("AI_SAVE_OUTCOME") != "success":
        receipt.update(status="FAIL_SAVE", reason="DATA_BRANCH_PUBLICATION_FAILED")
    else:
        receipt.update(persisted=counts["processed"], persisted_success=counts["success"])
        if counts["error"]:
            receipt["reason"] = "ARTICLE_ERRORS_PERSISTED"
        else:
            receipt.update(status="ANALYSIS_PASS", reason="ANNOTATED_AND_PERSISTED")
    return receipt


def report(env, output):
    receipt = classify(env)
    encoded = json.dumps(receipt, sort_keys=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    if env.get("GITHUB_STEP_SUMMARY"):
        with Path(env["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
            summary.write(
                f"RSS AI outcome: **{receipt['status']}** ({receipt['reason']}). "
                f"Processed {receipt['processed']}; valid annotations {receipt['success']}; "
                f"article errors {receipt['error']}; persisted rows {receipt['persisted']}; "
                f"persisted valid annotations {receipt['persisted_success']}.\n")
    return int(receipt["status"].startswith("FAIL_"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(report(os.environ, args.output))
