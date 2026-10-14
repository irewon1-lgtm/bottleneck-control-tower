"""Offline stage-3 review of the saved actual response; never calls an API.

The manually reviewed development answers are not a stage-4 evaluation set.
The source ledger is opened read-only; review jobs go to a separate V4 copy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from bct.v4.free_ai import Router, QUOTE_SCHEMA, SYSTEM, VERSION, source_input
from bct.v4.semantics import VERSION as SEMANTIC_VERSION
from bct.v4.store import Ledger, sha


class NoNetwork:
    def call(self, *args, **kwargs):
        raise AssertionError("OFFLINE_REVIEW_CANNOT_CALL_API")


def field_value(item, field):
    if field == "entity":
        return item["entity"]["value"]
    if field in ("kind", "role", "actuality"):
        return item[field]
    return next((fact["value"] for fact in item["facts"] if fact["field"] == field), None)


def compare(items, gold):
    observations = {key: [] for key in ("correct_adoptions", "incorrect_adoptions", "omissions", "unknown_preserved")}
    for answer in gold["items"]:
        index = answer["input_item_index"]
        item = items[index]
        for field, expected in answer["expected"].items():
            actual = field_value(item, field)
            row = {"item_index": index, "field": field, "expected": expected, "actual": actual}
            expected_unknown = expected is None or field in ("kind", "role", "actuality") and expected == "UNKNOWN"
            actual_unknown = actual is None or field in ("kind", "role", "actuality") and actual == "UNKNOWN"
            category = ("unknown_preserved" if expected_unknown and actual_unknown else
                        "correct_adoptions" if actual == expected else
                        "omissions" if actual_unknown else "incorrect_adoptions")
            observations[category].append(row)
        for mention in answer.get("mentioned_but_not_extracted", []):
            name = "entity" if mention["field"] == "entity_mention" else mention["field"]
            if field_value(item, name) is None:
                observations["omissions"].append({"item_index": index, **mention,
                                                  "reason": "Literal source mention omitted; no fact fabricated to fill it"})
    return {"definition": "UNKNOWN counts both null fields and UNKNOWN kind/role/actuality labels; known values/types/events count as correct adoptions",
            "counts": {key: len(rows) for key, rows in observations.items()},
            "assessed_gold_fields": sum(len(x["expected"]) for x in gold["items"]),
            "additional_mention_checks": sum(len(x.get("mentioned_but_not_extracted", [])) for x in gold["items"]),
            "observations": observations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path("var/v4/groq-stage2/live"))
    parser.add_argument("--root", type=Path, default=Path("var/v4/stage3/replay"))
    parser.add_argument("--config", type=Path, default=Path("var/v4/groq-stage2/trial-config.json"))
    parser.add_argument("--output", type=Path, default=Path("var/v4/stage3/official-replay.json"))
    args = parser.parse_args()
    fixture_dir = Path(__file__).resolve().parents[2] / "tests/fixtures"
    fixture = json.loads((fixture_dir / "v4_stage3_official_source.json").read_text())
    gold = json.loads((fixture_dir / "v4_stage3_gold.json").read_text())
    assert hashlib.sha256(fixture["document"]["body"].encode()).hexdigest() == gold["source_body_sha256"]
    assert hashlib.sha256(fixture["response_text"].encode()).hexdigest() == gold["response_sha256"]
    config = json.loads(args.config.read_text())
    assert config["providers"] == ["groq"]
    source_path = (args.source_root / "v4.sqlite3").resolve()
    review_path = (args.root / "v4.sqlite3").resolve()
    assert source_path != review_path, "SOURCE_LEDGER_MUST_REMAIN_READ_ONLY"
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source_db:
        assert source_db.execute("SELECT value FROM metadata WHERE key='format'").fetchone()[0] == "bct-v4-ledger-1"
        before = source_db.execute("SELECT count(*) FROM events WHERE kind='API_ATTEMPT'").fetchone()[0]
        if not review_path.exists():
            args.root.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(review_path) as target:
                source_db.backup(target)
    ledger = Ledger(args.root)
    try:
        with ledger.worker():
            router = Router(ledger, config, adapter=NoNetwork())
            doc = next(d for d in ledger.latest_documents() if d["document_id"] == fixture["document"]["document_id"])
            assert doc["body"] == fixture["document"]["body"]
            assert hashlib.sha256(ledger.db.execute("SELECT data FROM blobs WHERE id=?", (doc["raw_sha256"],)).fetchone()[0]).hexdigest() == doc["raw_sha256"]
            selected = source_input(router.reviewed_document(doc), config, router.env)
            assert selected == fixture["selected_input"]
            key = sha([VERSION, SYSTEM, QUOTE_SCHEMA, selected, doc["body_sha256"]])
            saved = [x for x in router.events("API_RESPONSE") if x["input_key"] == key and x["provider"] == "groq"]
            assert saved and saved[-1]["text"] == fixture["response_text"], "MATCHING_SAVED_RESPONSE_REQUIRED"
            value = router.read(doc, probe_provider="groq")
            assert value["status"] == "PASS" and value["cached"] and router.calls == 0
            result = value["result"]
            current = compare(result["items"], gold)
            assert not current["observations"]["incorrect_adoptions"]
            assert all(x["s_stage"] == "UNKNOWN" and not x["forecast_candidate"] for x in result["items"])
            report = {"scope": "ONE_OFFICIAL_DOCUMENT_THREE_SAVED_REAL_RESPONSE_ITEMS; development smoke only",
                "semantic_policy_version": SEMANTIC_VERSION, "gold_authority": gold["authority"],
                "gold_sha256": hashlib.sha256((fixture_dir / "v4_stage3_gold.json").read_bytes()).hexdigest(),
                "source_body_sha256": doc["body_sha256"], "source_raw_sha256": doc["raw_sha256"],
                "response_sha256": fixture["response_sha256"], "source_published_at": doc["published_at"],
                "source_status": result["source_status"], "semantic_accuracy": "UNKNOWN_GENERAL",
                "before_raw_groq": compare(json.loads(fixture["response_text"])["items"], gold),
                "after_semantic_guards": current, "result": result,
                "generation_calls": 0, "input_tokens": 0, "output_tokens": 0, "api_cost_usd": 0,
                "historical_response_usage_reused_not_new": fixture["usage"],
                "source_ledger_attempts_before": before,
                "review_ledger_attempts_after": len(router.events("API_ATTEMPT")),
                "storage": "PASS_NEW_SEMANTIC_JOB_IN_SEPARATE_SQLITE",
                "stage4_started": False, "shadow_started": False,
            }
            assert report["review_ledger_attempts_after"] == before
            router.record("SEMANTIC_REVIEW", report)
        report["stored_review_count"] = len(router.events("SEMANTIC_REVIEW"))
        assert ledger.db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        ledger.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"source_status": report["source_status"], "after_counts": current["counts"],
                      "generation_calls": 0, "storage": report["storage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
