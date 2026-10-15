"""Real saved recovery ledgers: source integrity and no-candidate promotion."""
import gzip
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from bct.v4.dashboard import ResearchReader
from bct.v4.dashboard_research import load_recovery

ROOT = Path(__file__).resolve().parents[1]


def test_latest_post_ui_and_cpu_sources_are_both_visible_and_still_not_forecasts():
    reader = ResearchReader(ROOT)
    result = reader.dashboard()
    assert result["counts"]["body_nonempty"] == 235
    assert result["counts"]["pending"] == 2
    assert result["counts"]["evidence"] == 511
    assert result["counts"]["reviewed"] == 23
    assert result["counts"]["future_candidates"] == {"S1": 0, "S2": 0, "S3": 0}
    recovery = result["research_updates"]["cpu_recovery"]
    assert recovery["summary"]["documents_processed"] == 38
    assert recovery["summary"]["actually_CPU_read_characters"] == 230111
    assert recovery["summary"]["body_characters"] == 231283
    assert recovery["summary"]["new_official_primary_verified_events"] == 0
    assert sum(r["category"] == "cpu_product" for r in recovery["records"]) == 1186
    assert sum(r["category"] == "reported" for r in recovery["records"]) == 6
    assert len({r["id"] for r in recovery["records"]}) == 1192
    assert all(not r["is_future_candidate"] and r["stage"] == "UNKNOWN" for r in recovery["records"])
    assert result["data_at"] >= recovery["at"]
    for category in ("cpu_product", "reported"):
        row = next(r for r in recovery["records"] if r["category"] == category)
        detail = reader.evidence(row["id"])
        assert detail["all_references_verified"] is True
        assert all(ref["quote"] for ref in detail["references"])
        assert "승격하지 않았습니다" in detail["counterpart_note"]


@pytest.mark.parametrize("damage", ["archive_hash", "table_digest", "report_count"])
def test_inconsistent_research_bundle_is_rejected(tmp_path, damage):
    target = tmp_path / "docs/v4/cpu-recovery"
    target.mkdir(parents=True)
    for name in ("research-snapshot.sqlite3.gz", "storage-proof.json", "RESULTS.json"):
        shutil.copyfile(ROOT / "docs/v4/cpu-recovery" / name, target / name)
    path = target / ("RESULTS.json" if damage == "report_count" else "storage-proof.json")
    d = json.loads(path.read_text())
    if damage == "archive_hash":
        d["snapshot_sha256"] = "0" * 64
    elif damage == "table_digest":
        d["tables"]["documents"]["sha256"] = "0" * 64
    else:
        d["CPU_product_proposals_retained"] += 1
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="불일치"):
        load_recovery(tmp_path)


def test_recovery_source_archive_bytes_are_unchanged_by_reads():
    path = ROOT / "docs/v4/cpu-recovery/research-snapshot.sqlite3.gz"
    before = path.read_bytes()
    load_recovery(ROOT)
    assert path.read_bytes() == before
