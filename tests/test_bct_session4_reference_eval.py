"""Regression guarantees for retrospective AI-reference evaluation.

Evaluated rules are fixed in Session 3. Tests cannot change reference labels.
"""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


def load():
    spec=importlib.util.spec_from_file_location(
        "s4_reference",ROOT/"tools/bct_session4_reference_eval.py")
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def record(id,paths="",body="NOT_IN_SIDECAR",combined="Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING",
           priority="P4_NO_METADATA_CUE",prior=False,source="site.example"):
    return {"id":id,"source":source,"url":"https://"+source+"/news/"+id,
            "title":"Example article "+id, "published_at":"2026-10-01",
            "metadata_priority":priority,"combined_review_lane":combined,
            "title_snippet_signal_paths":paths,"previous_body_status":body,
            "previous_body_candidate_unverified":"True" if prior else "False"}


def test_unknown_reference_is_never_false_negative_or_true_negative():
    s=load()
    value=s.metrics([("TRUE",True),("FALSE",True),("TRUE",False),
                     ("FALSE",False),("UNKNOWN",True),("UNKNOWN",False)])
    assert (value["TP"],value["FP"],value["FN"],value["TN"])==(1,1,1,1)
    assert value["UNKNOWN_REFERENCE"]==2
    assert value["measurable"]==4 and value["total"]==6
    assert value["precision"]==.5 and value["recall"]==.5


def test_zero_denominator_never_passes_by_vacuous_truth():
    s=load()
    value=s.metrics([("FALSE",False),("UNKNOWN",True)])
    assert value["precision"] is None
    assert value["recall"] is None
    assert value["f1"] is None
    assert value["UNKNOWN_REFERENCE"]==1


def test_full_body_queue_rescues_headline_p4_as_a_lead_only():
    s=load()
    prior=record("doc","",body="FULL",combined="Q1_PRIOR_FULL_BODY_LEAD",prior=True)
    ref={"docs":{"doc":{"id":"doc","url":prior["url"],"source":prior["source"],
                          "labels":{"DEMAND":"TRUE","SUPPLY":"FALSE","RELIEF":"FALSE"}}},
         "sample_id":"one"}
    report,errors=s.evaluate([prior],{"regression":ref})
    assert report["aggregate"]["P4_hidden_reference"]["P4_reference_positive_rescued_by_prior_full_body"]==1
    assert report["aggregate"]["metrics"]["metadata_paths"]["DEMAND"]["FN"]==1
    assert report["aggregate"]["metrics"]["combined_any"]["ANY"]["TP"]==1
    assert report["signal_validation_target"]=="RSS_TITLE_SNIPPET_FIRSTPASS_NOT_FUTURE_BOTTLENECK"
    assert report["candidate_promotion"]==0 if "candidate_promotion" in report else report["source_db_writes"]==0
    assert errors[0]["error"]=="FALSE_NEGATIVE"


def test_different_source_url_does_not_silently_match_same_id():
    s=load()
    article=record("doc","DEMAND")
    label={"docs":{"doc":{"id":"doc","url":"https://different.example/story",
                          "source":article["source"],
                          "labels":{"DEMAND":"TRUE","SUPPLY":"TRUE","RELIEF":"TRUE"}}}}
    result,errors=s.evaluate([article],{"regression":label})
    assert result["aggregate"]["matched"]==0
    assert result["aggregate"]["not_comparable_count"]==1
    assert result["status"]=="BLOCKED_INSUFFICIENT_COMPARABLE_AI_REFERENCE"
    assert errors==[]


def test_new_blind_packet_hides_all_prior_result_fields_and_historical_ids():
    s=load()
    rows=[record(f"doc{i}",source=f"src{i%8}.example",
                 paths="SUPPLY",combined="Q4_METADATA_SIGNAL_NEEDS_SOURCE",
                 priority="P2_TEXT_CUE") for i in range(260)]
    packet=s.frozen_blind_packet(rows,{"doc0","doc1"},count=240)
    assert len(packet)==240
    assert len(set(r["id"] for r in packet))==240
    assert not {"doc0","doc1"} & set(r["id"] for r in packet)
    assert len({r["source"] for r in packet})==8
    assert [r["id"] for r in packet]==[
        r["id"] for r in s.frozen_blind_packet(rows,{"doc0","doc1"},count=240)]


def test_reference_label_type_and_spreadsheet_formula_safety():
    s=load()
    with pytest.raises(ValueError,match="REFERENCE_LABEL_INVALID"):
        s.strict_label("maybe")
    assert s.strict_label({"value":"TRUE"})=="TRUE"
    assert s.any_truth({"DEMAND":"FALSE","SUPPLY":"FALSE","RELIEF":"FALSE"})=="FALSE"
    assert s.any_truth({"DEMAND":"UNKNOWN","SUPPLY":"FALSE","RELIEF":"FALSE"})=="UNKNOWN"
    assert s.cell("=2+2")=="'=2+2"
    assert s.cell("@cmd")=="'@cmd"
