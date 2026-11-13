"""Historical RSS full-body QA vs. current Future screening must stay separate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("v4_future_sidecar_index", ROOT/"tools/v4_future_sidecar_index.py")
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    digest="f"*64
    manifest={
        "format":"bct-sharded-sidecar-v1",
        "document_sha256":digest,
        "item_counts":{"results":21,"hypotheses":4,"events":3,"objective_version":1},
        "total_item_count":29,
        "shards":[
            {"path":f"future-candidates.shards/{digest}/future-candidates.part-001.json",
             "sha256":"e"*64,"git_sha":"b"*40,"item_count":29}
        ]
    }
    return manifest


def test_index_count_is_not_sector_evidence_count():
    x=module.summarize(fixture(),commit_sha="a"*40,blob_sha="c"*40)
    assert x["status"]=="VERIFIED_INDEX_ONLY_NOT_ANALYSIS_COMPLETE"
    assert x["registered_screening_record_slots"]==21
    assert x["unverified_hypothesis_slots"]==4
    assert x["grouped_event_slots"]==3
    assert x["shards_verified_in_this_read"]==0
    assert x["qualification"]=="SCREENING_STORAGE_NOT_ORIGINAL_SOURCE_OR_VERIFIED_BOTTLENECK"
    assert not any("forecast_score" in k or "evidence_count" in k for k in x)


@pytest.mark.parametrize("change",[
    lambda m:m.update(total_item_count=28),
    lambda m:m["shards"][0].update(item_count=28),
    lambda m:m["shards"][0].update(sha256="not-sha256"),
    lambda m:m["shards"][0].update(path="../escape.json"),
    lambda m:m.update(format="bct-invalid"),
    lambda m:m["item_counts"].update(results=-2),
])
def test_corrupt_manifest_cannot_claim_verified_index(change):
    value=fixture()
    change(value)
    with pytest.raises(ValueError):
        module.summarize(value,commit_sha="a"*40,blob_sha="c"*40)


def test_pinned_full_corpus_audit_is_a_held_unverified_snapshot():
    audit=json.loads((ROOT/"docs/v4/live-screening-audit-20261113.json").read_text(encoding="utf-8"))
    assert audit["status"]=="PASS_READ_ONLY_QUEUE_RECONCILIATION"
    assert audit["classification"]=="PINNED_AUDIT_NOT_CURRENT_PROCESSING_RECEIPT_NOT_VERIFIED_SHORTAGE"
    assert audit["rss_articles"]==sum(audit["body_counts"].values())==10604
    assert audit["sidecar_results"]+audit["unlinked"]==10604
    assert audit["selected_future_work"]=={"total":100,"recent":42,"older":58,"completed_in_this_audit":0}
    assert audit["due_source_recheck"]==739
    assert audit["blocked_or_deferred"]==4138


def test_runtime_funnel_preserves_existing_research_rank():
    exporter=(ROOT/"tools/v4_dashboard_static_export.py").read_text(encoding="utf-8")
    checker=(ROOT/"tools/v4_dashboard_static_check.py").read_text(encoding="utf-8")
    app=(ROOT/"src/bct/v4/dashboard_web/app.js").read_text(encoding="utf-8")
    assert 'data["sector_rankings"] = ranks(data["records"])' in exporter
    assert 'data["source_backlog"]' in exporter
    assert '"rank_input_not_increased_by_rss": True' in exporter
    assert 'audit["selected_future_work"]["completed_in_this_audit"] != 0' in exporter
    assert 'shards_verified_in_this_read' in (ROOT/"tools/v4_future_sidecar_index.py").read_text()
    assert 'function sourceBacklogPanel()' in app
    assert 'page.append(sourceBacklogPanel());' in app
    assert 'data["sector_rankings"]==ranks(data["records"])' in checker
