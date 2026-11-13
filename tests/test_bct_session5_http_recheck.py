"""Session 5 targeted HTTP-only recheck protects all 293 unchanged records."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
def mod():
    spec=importlib.util.spec_from_file_location(
        "s5reconcile",ROOT/"tools/bct_session5_http_recheck.py")
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

def fixture():
    old=[];blind=[]
    for i in range(302):
        ident=f"doc-{i:03d}"
        http=i<9
        url=("http" if http else "https")+f"://test.example/{ident}"
        blind.append({"document_id":ident,"url":url,"source":"test.example"})
        old.append({
            "document_id":ident,"source_url":url,
            "pilot_status":"ACCESS_OR_EXTRACTION_ERROR" if http else "PARTIAL_ORIGINAL",
            "access_classification":"COLLECTOR_ERROR" if http else "HTTP_200",
            "error_type":"ValueError" if http else "",
            "body_sha256":"a"*64 if http else "",
            "S1_S2_S3":"False","labels":"UNKNOWN"})
    return old,blind

def test_select_exactly_nine_before_any_network():
    s=mod()
    old,blind=fixture()
    selected=s.eligible(old,blind)
    assert len(selected)==9 and all(r["url"].startswith("http://") for r in selected)
    assert not any(x["document_id"]=="doc-010" for x in selected)

def test_refuses_to_refetch_real_http_403_and_other_hosts():
    s=mod()
    old,blind=fixture()
    old[0]["access_classification"]="HTTP_403"
    with pytest.raises(ValueError,match="EXPECT_EXACT_9"):
        s.eligible(old,blind)

def test_refuses_changed_id_url_pair_and_partial_source():
    s=mod()
    old,blind=fixture();blind[1]["url"]="http://different.example/mismatch"
    with pytest.raises(ValueError,match="NOT_MATCHED"):
        s.eligible(old,blind)

def test_reconcile_stays_302_and_retains_293_old_records():
    s=mod();old,blind=fixture()
    selected=s.eligible(old,blind)
    fresh=[{"document_id":r["document_id"],"pilot_status":"FULL_UNVERIFIED_ORIGINAL",
            "S1_S2_S3":False,"labels":"UNKNOWN"} for r in selected]
    result,count=s.reconcile(old,fresh,expected_ids=[r["document_id"] for r in selected])
    assert len(result)==302
    assert count["FULL_UNVERIFIED_ORIGINAL"]==9
    assert count["PARTIAL_ORIGINAL"]==293
    assert sum(r.get("rechecked_in_session5")=="true" for r in result)==9
    assert next(r for r in result if r["document_id"]=="doc-009")["pilot_status"]=="PARTIAL_ORIGINAL"
    assert all(str(r["S1_S2_S3"]).lower()=="false" for r in result)

def test_never_reconcile_a_promoted_stage():
    s=mod();old,blind=fixture()
    nine=s.eligible(old,blind)
    fresh=[{"document_id":r["document_id"],"pilot_status":"VERIFIED_FULL",
            "S1_S2_S3":True} for r in nine]
    with pytest.raises(ValueError,match="UNVERIFIED_PROMOTION"):
        s.reconcile(old,fresh,expected_ids=[r["document_id"] for r in nine])
