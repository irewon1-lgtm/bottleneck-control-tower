"""Newest original-source capture is evidence-bound and distinct from ranked research."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
SPEC=importlib.util.spec_from_file_location("v4_source_intake_public", ROOT/"tools/v4_source_intake_public.py")
source=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def example():
    receipt={
        "format":"bct-public-acquisition-1",
        "repository":"irewon1-lgtm/bottleneck-control-tower",
        "run_id":43245595579,"run_attempt":1,"head_sha":"a"*40,
        "RSS_run_id":43243530759,"RSS_run_attempt":1,
        "RSS_manifest_sha256":"b"*64,
        "collection_started_at":"2026-11-12T15:02:48+00:00",
        "acquisition_started_at":"2026-11-12T15:14:15+00:00",
        "completed_at":"2026-11-12T15:20:04.944659+00:00",
        "scope_reader_version":"source-scope-reader-5",
        "counts":{
            "new_URLs":32,"new_seed_attempts":32,
            "new_seed_statuses":{"CAPTURED":13,"PROVENANCE_BLOCKED":16,"HTTP_403":2,"TIMEOUT":1},
            "new_verified_documents":13,"additional_bodies_acquired":0,
            "valid_additional_primary_documents":0,
            "body_HTTP_requests":None,"body_pending":None
        },
        "units":{
            "new_seed_attempts":"SEED_CAPTURE_OUTCOMES_NOT_HTTP_REQUESTS",
            "new_verified_documents":"NEW_SOURCE_VERIFIED_DOCUMENTS",
            "new_seed_statuses":"SEED_CAPTURE_OUTCOMES_BY_FIXED_CODE"
        },
        "source_integrity_state":"PARTIAL_HOLD","unverified_source_holds":1,
        "objective_version":"bct-objective-1",
        "objective_sha256":"0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7"
    }
    index={
        "format":"bct-new-precursor-collection-v1",
        "cache_run_id":"43245595579","cache_run_attempt":1,
        "completed_at":receipt["completed_at"],
        "scope_reader_version":receipt["scope_reader_version"],
        "source_integrity_state":receipt["source_integrity_state"],
        "unverified_source_holds":receipt["unverified_source_holds"],
        "new_seed_attempts":32,"new_verified_documents":13,
        "new_seed_statuses":receipt["counts"]["new_seed_statuses"],
        "additional_bodies_acquired":0,"valid_additional_primary_documents":0
    }
    run={
        "name":"New precursor evidence acquisition",
        "path":".github/workflows/precursor-acquisition.yml",
        "status":"completed","conclusion":"success",
        "id":43245595579,"run_attempt":1,"head_branch":"main","head_sha":"a"*40,
        "event":"workflow_dispatch",
        "head_repository":{"full_name":"irewon1-lgtm/bottleneck-control-tower"}
    }
    raw=json.dumps(receipt,separators=(",",":"),sort_keys=True).encode()+b"\n"
    manifest={"format":"bct-public-acquisition-manifest-1",
              "file":"snapshot.json","bytes":len(raw),
              "sha256":hashlib.sha256(raw).hexdigest()}
    return index,run,raw,manifest


def check(index,run,raw,manifest,**kwargs):
    return source.verify_receipt(index,run,raw,manifest,data_commit="c"*40,
                                 rss_run_id=kwargs.get("rss_run_id",43243530759))


def test_actual_counter_contract_and_older_auto_receipt_is_not_rebranded():
    index,run,raw,manifest=example()
    r=check(index,run,raw,manifest)
    assert r["status"]=="VERIFIED_PUBLIC_SOURCE_INTAKE"
    assert r["source_event"]=="workflow_dispatch"
    assert r["source_run_id"]==43245595579 and r["rss_run_id"]==43243530759
    assert r["matches_current_rss"] is True
    assert (r["seed_attempts"],r["captured"],r["held"])==(32,13,19)
    assert r["valid_additional_primary_documents"]==0
    assert r["statuses"]["PROVENANCE_BLOCKED"]==16
    assert r["classification"]=="CAPTURED_SOURCE_DOCUMENTS_NOT_VERIFIED_BOTTLENECKS"
    assert "articles" not in r and "records" not in r


def test_fails_closed_on_wrong_artifact_bytes_or_changed_counts():
    index,run,raw,manifest=example()
    with pytest.raises(ValueError,match="ARTIFACT_HASH"):
        check(index,run,raw+b" ",manifest)
    index["new_verified_documents"]=14
    with pytest.raises(ValueError,match="INDEX_ARTIFACT"):
        check(index,run,raw,manifest)


@pytest.mark.parametrize("field,value",[
    ("event","pull_request"),("head_branch","qa/bad"),("conclusion","failure"),
    ("run_attempt",2),("path",".github/workflows/other.yml"),
])
def test_manual_source_producer_must_be_exact(field,value):
    index,run,raw,manifest=example()
    run[field]=value
    with pytest.raises(ValueError,match="INVALID_PRODUCER"):
        check(index,run,raw,manifest)


def test_later_rss_does_not_misrepresent_the_previous_capture():
    index,run,raw,manifest=example()
    r=check(index,run,raw,manifest,rss_run_id=43299999999)
    assert not r["matches_current_rss"]
    with pytest.raises(ValueError,match="TIME_ORDER"):
        check(index,run,raw,manifest,rss_run_id=11111111)


def test_original_readonly_static_projection_remains_separate():
    exporter=(ROOT/"tools/v4_dashboard_static_export.py").read_text(encoding="utf-8")
    app=(ROOT/"src/bct/v4/dashboard_web/app.js").read_text(encoding="utf-8")
    checker=(ROOT/"tools/v4_dashboard_static_check.py").read_text(encoding="utf-8")
    assert 'data["sector_rankings"] = ranks(data["records"])' in exporter
    assert 'data["latest_source_capture"]' in exporter
    assert 'api/source-intake.json' in exporter
    assert 'source_intake_sha256' in checker
    assert "function sourceIntakePanel()" in app
    assert "data.latest_source_capture" in app
    assert "source_capture" not in (ROOT/"src/bct/v4/sector_ranking.py").read_text(encoding="utf-8")
