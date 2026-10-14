"""Verify frozen stage-4 source files without network, models or adjudication."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from bct.v4.store import sha


def verify(path):
    manifest = json.loads(Path(path).read_text())
    digest = manifest.pop("freeze_sha256")
    if sha(manifest) != digest:
        raise ValueError("FREEZE_HASH_MISMATCH")
    rows = manifest["documents"]
    if len(rows) != 50 or Counter(r["split"] for r in rows) != {"development": 30, "evaluation": 20}:
        raise ValueError("CORPUS_SPLIT_COUNT_MISMATCH")
    for key in ("url", "document_id", "body_sha256"):
        if len({r[key] for r in rows}) != 50:
            raise ValueError("DUPLICATE_" + key.upper())
    native = partial_text = 0
    today = datetime.now(timezone.utc).date()
    for row in rows:
        body_bytes = Path(row["body_path"]).read_bytes()
        body = body_bytes.decode()
        if hashlib.sha256(body_bytes).hexdigest() != row["body_sha256"] or len(body) != row["body_characters"]:
            raise ValueError("SOURCE_BODY_HASH_OR_LENGTH_MISMATCH")
        if not row["publication_proof"] or datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")).date() > today:
            raise ValueError("UNVERIFIED_OR_FUTURE_PUBLICATION")
        proof = row["publication_proof"]
        if row.get("raw_path"):
            raw = gzip.decompress(Path(row["raw_path"]).read_bytes())
            if hashlib.sha256(raw).hexdigest() != row["raw_sha256"]:
                raise ValueError("NATIVE_HASH_MISMATCH")
            native += 1
            if "native_character_start" in proof:
                text = raw.decode(errors="replace")
                if text[proof["native_character_start"]:proof["native_character_end"]] != proof["literal_evidence"]:
                    raise ValueError("PUBLICATION_NATIVE_QUOTE_MISMATCH")
            elif proof.get("literal_evidence") and proof["literal_evidence"] not in body:
                raise ValueError("PUBLICATION_BODY_QUOTE_MISMATCH")
        else:
            partial_text += 1
            if row["body_status"] != "PARTIAL" or body.count(proof["literal_evidence"]) != 1:
                raise ValueError("RESTORED_TEXT_SCOPE_OR_PUBLICATION_MISMATCH")
            if row["url"] not in proof["literal_evidence"]:
                raise ValueError("RESTORED_ORIGIN_URL_NOT_LITERAL")
        if row["split"] == "evaluation" and row["prior_development_use"]:
            raise ValueError("DEVELOPMENT_SOURCE_IN_EVALUATION")
        if row["AI_result_viewed_before_freeze"] or row["old_results_used_as_gold"]:
            raise ValueError("EVALUATION_OR_GOLD_LEAKAGE")
        if row["AI_read_ranges_this_task"] or row["AI_unread_ranges_this_task"] != [{"start": 0, "end": len(body)}]:
            raise ValueError("CURRENT_READING_COVERAGE_MISMATCH")
    return {"status": "PASS_SOURCE_FILES_AND_FREEZE_INTEGRITY_ONLY",
            "documents": 50, "development": 30, "evaluation": 20,
            "FULL": sum(r["body_status"] == "FULL" for r in rows),
            "PARTIAL": sum(r["body_status"] == "PARTIAL" for r in rows),
            "native_HTML_snapshots": native, "restored_extracted_text": partial_text,
            "freeze_sha256": digest, "new_Groq_calls": 0,
            "product_role_quantity_customer_time_gold": "UNVERIFIED",
            "model_accuracy": "NOT_RUN", "CPU_improvement": "BLOCKED",
            "early_bottleneck_performance": "NOT_RUN_STAGE6"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("docs/v4/stage4-corpus/manifest.json"))
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), ensure_ascii=False))
