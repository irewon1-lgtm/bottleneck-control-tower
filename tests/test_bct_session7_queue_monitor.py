"""Session 7: immutable full-RSS work ledger, no evidence promotion."""
from datetime import datetime, timezone, timedelta
import pytest

from tools import bct_session7_queue_monitor as s7

NOW=datetime(2026,11,13,2,0,tzinfo=timezone.utc)

def row(i,title="Ordinary news update",hours=2):
    t=(NOW-timedelta(hours=hours)).isoformat()
    return {"id":str(i),"source":"news.example","title":title,
            "snippet":"","url":f"https://news{i%8}.example/article/{i}",
            "collected_at":t,"updated_at":t,"published_at":t}

def test_full_body_prior_lead_cannot_be_demoted_by_title_p4():
    old={"body_status":"FULL","candidate":True,"decision":"CONTEXT_REVIEW",
         "fingerprint":"some-old-version"}
    r=s7.classify(row(4),old,NOW)
    assert r["review_lane"]=="Q1_PRIOR_FULL_BODY_LEAD"
    assert r["work_action"]=="REVIEW_VERIFIED_BODY_PROVENANCE"
    assert r["independent_supply_demand_pair_verified"] is False
    assert r["S1_S2_S3_verified_from_this_run"] is False

def test_recovery_of_unprocessed_new_rss_and_existing_backlog_both_get_slots():
    rows=[row(i,"New orders for solid rocket motors increased by 40%",hours=2 if i<20 else 800)
          for i in range(40)]
    ledger,work,summary=s7.reconcile(rows,{},NOW,budget=20)
    assert len(ledger)==40
    assert summary["articles_without_sidecar"]==40
    assert len(work)==20
    assert summary["selected_recent"]==8
    assert summary["selected_older"]==12
    assert summary["new_full_article_downloads"]==0
    assert summary["candidate_promotions"]==0
    assert len(set(r["article_id"] for r in work))==20

def test_existing_blocked_article_does_not_repeatedly_attempt_http_403():
    article=row(1)
    prior={"body_status":"UNAVAILABLE",
           "source_version":"old",
           "reasons":["HTTP_403"],"candidate":False,
           "fingerprint":s7.sha((article["url"]+article["updated_at"]).encode())}
    r=s7.classify(article,prior,NOW)
    assert r["work_action"]=="HOLD_SOURCE_ACCESS"
    _,work,summary=s7.reconcile([article],{"1":prior},NOW)
    assert len(work)==0 and summary["blocked_or_deferred"]==1

def test_rate_limit_and_due_retry_are_visible_not_implicitly_done():
    a=row(1);fp=s7.sha((a["url"]+a["updated_at"]).encode())
    future=(NOW+timedelta(hours=5)).isoformat()
    prior={"body_status":"UNAVAILABLE","fingerprint":fp,"retry_after":future,
           "attempts":1,"candidate":False}
    r=s7.classify(a,prior,NOW)
    assert r["work_action"]=="WAIT_RETRY_AFTER"
    r2=s7.classify(a,{**prior,"retry_after":""},NOW)
    assert r2["work_action"]=="FETCH_OR_RECHECK_ORIGINAL"
    r3=s7.classify(a,{**prior,"attempts":3},NOW)
    assert r3["work_action"]=="HOLD_ATTEMPT_LIMIT"

def test_source_change_can_release_access_hold_but_not_verify_old_proof():
    a=row(1);prior={"body_status":"UNAVAILABLE","fingerprint":"prior",
           "reasons":["HTTP_403"],"attempts":3}
    r=s7.classify(a,prior,NOW)
    assert r["source_updated_since_old_screen"]
    assert r["work_action"]=="FETCH_OR_RECHECK_ORIGINAL"
    assert not r["original_provenance_verified"]

def test_old_corpus_still_has_service_when_all_articles_same_host():
    rows=[row(i) for i in range(80)]
    for i,r in enumerate(rows):r["url"]=f"https://news{i%8}.example/{i}"
    ledger,work,_=s7.reconcile(rows,{},NOW,budget=40)
    assert len(work)<=40
    assert len({r["article_id"] for r in work})==len(work)
    assert max(sum(w["url"].startswith(f"https://news{i}.example/") for w in work)
               for i in range(8))<=6

def test_can_never_claim_unprocessed_articles_were_read():
    a=row(1)
    r=s7.classify(a,None,NOW)
    assert r["body_status"]=="NOT_IN_SIDECAR"
    assert r["work_action"]=="FETCH_OR_RECHECK_ORIGINAL"
    assert not r["sidecar_record_present"]
    assert r["independent_supply_demand_pair_verified"] is False

def test_duplicate_or_orphan_fail_closed():
    a=row(1)
    with pytest.raises(ValueError,match="RSS_ID_UNIQUE"):
        s7.reconcile([a,a],{},NOW)
    with pytest.raises(ValueError,match="SIDECAR_ORPHAN"):
        s7.reconcile([a],{"not-in-rss":{"body_status":"FULL"}},NOW)

def test_csv_injection_is_escaped():
    assert s7.csv_cell("=1+1")=="'=1+1"
    assert s7.csv_cell("@cmd")=="'@cmd"
    assert s7.csv_cell("genuine")=="genuine"
