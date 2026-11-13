"""Session 3 coverage checks: every title/snippet classified, no invented body/target certainty."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import pytest

def module():
    path=Path(__file__).resolve().parents[1]/"tools"/"bct_session3_firstpass.py"
    spec=spec_from_file_location("bct_session3_firstpass",path)
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def row(ident,title,snippet="",url=None):
    return {"id":ident,"source":"example.org","url":url or "https://example.org/"+ident,
            "title":title,"snippet":snippet,"published_at":"2026-11-12T09:00:00Z",
            "collected_at":"2026-11-13T09:00:00Z"}

def test_metadata_firstpass_is_not_verified_evidence_even_with_multiple_cues():
    item=module().triage_one(row("a","Power transformer lead times extend as new orders surge"),
                              {"body_status":"FULL","candidate":True,"decision":"CONTEXT_REVIEW"})
    assert item["metadata_classification"]=="TITLE_SNIPPET_ONLY"
    assert item["previous_body_status"]=="FULL"
    assert item["prior_body_screened"] is True
    assert item["previous_body_candidate_unverified"] is True
    assert item["stage"]=="NOT_EVALUATED"
    assert item["final_bottleneck_verified"] is False
    assert item["prior_review_required"] is True
    assert item["narrow_signal_codes"]

def test_headline_noise_does_not_become_target():
    item=module().triage_one(row("a","CPU software algorithm increases data latency efficiency"))
    assert item["previous_body_status"]=="NOT_IN_SIDECAR"
    assert item["final_bottleneck_verified"] is False
    assert item["metadata_classification"]=="TITLE_SNIPPET_ONLY"

def test_all_articles_are_reconciled_to_one_of_four_prior_body_states():
    rows=[row("a","Power transformer supply shortages expected in 2028"),
          row("b","Factory expansion adds capacity"),
          row("c","Demand for copper rises"),
          row("d","New market survey published"),
          row("e","Shipping production delayed")]
    sidecar={"a":{"body_status":"FULL","candidate":True},
             "b":{"body_status":"PARTIAL"},
             "c":{"body_status":"UNAVAILABLE"},
             "d":{"body_status":"MYSTERY"}}
    records,metrics=module().evaluate(rows,sidecar)
    assert len(records)==5==metrics["screened_title_snippet"]
    assert metrics["no_prior_sidecar"]==1
    assert sum(metrics["previous_body_status"].values())==5
    assert metrics["previous_body_status"]["UNKNOWN"]==1
    assert metrics["source_document_bodies_newly_read"]==0
    assert metrics["candidate_promotion"]==0
    assert metrics["independent_supply_demand_verified"]=="NOT_MEASURED"
    assert len({r["id"] for r in records})==5

def test_duplicate_article_ids_and_unlinked_sidecar_fail_closed():
    m=module()
    with pytest.raises(ValueError,match="RSS_ID_NOT_UNIQUE"):
        m.evaluate([row("x","A"),row("x","B")],{})
    with pytest.raises(ValueError,match="SIDECAR_HAS_NONCANONICAL_IDS"):
        m.evaluate([row("x","A")],{"not-rss":{"body_status":"FULL"}})

def test_invalid_unreadable_metadata_fails_closed_and_csv_blocks_formula():
    m=module()
    with pytest.raises(ValueError,match="REQUIRED_FIELDS"):
        m.evaluate([row("x","")],{})
    assert m.safe_cell("=1+2").startswith("'")
    assert m.safe_cell("@danger").startswith("'")
    assert m.safe_cell("safe")=="safe"


def test_p4_without_headline_cues_keeps_prior_full_body_lead():
    m=module()
    x=m.triage_one(row("x","Ordinary company update"),
        {"body_status":"FULL","candidate":True,"decision":"CONTEXT_REVIEW"})
    assert x["metadata_priority"]=="P4_NO_METADATA_CUE"
    assert x["combined_review_lane"]=="Q1_PRIOR_FULL_BODY_LEAD"
    assert x["stage"]=="NOT_EVALUATED"
    assert not x["final_bottleneck_verified"]


def test_partially_captured_candidate_stays_a_hold_not_confirmed():
    m=module()
    rows=[row("x","Ordinary company update"),
          row("y","General commentary"),
          row("z","No information")]
    sidecar={
        "x":{"body_status":"FULL","candidate":True,"decision":"CANDIDATE_ONLY"},
        "y":{"body_status":"PARTIAL","candidate":True,"decision":"CONTEXT_REVIEW"},
        "z":{"body_status":"UNAVAILABLE","candidate":True,"decision":"UNREAD_MATERIAL"},
    }
    out,report=m.evaluate(rows,sidecar)
    assert out[0]["combined_review_lane"]=="Q1_PRIOR_FULL_BODY_LEAD"
    assert out[1]["combined_review_lane"]=="Q2_PRIOR_PARTIAL_BODY_LEAD"
    assert out[2]["combined_review_lane"]=="Q3_PRIOR_UNAVAILABLE_LEAD_HOLD"
    assert report["rescued_p4_using_prior_full_body_leads"]==1
    assert sum(report["combined_review_lanes"].values())==3
    assert all(not x["final_bottleneck_verified"] for x in out)
