"""BCT session 6: strict independently sourced demand/supply audit, never S-stage."""
from pathlib import Path
import csv
from hashlib import sha256
import threading
from types import SimpleNamespace
import pytest

from tools import bct_session6_cross_evidence as s6
from bct.future_body import extract_document


def original(ident="x",url="https://example.org/item",status="VERIFIED_FULL",
             body_sha="a"*64):
    return {
        "document_id":ident,"source_url":url,
        "source_host":"example.org","pilot_status":status,
        "body_sha256":body_sha,"provenance_verified":"True"
    }


def make_sample(tmp_path):
    path=tmp_path/"old.csv"
    fields=list(original())
    with path.open("w",newline="",encoding="utf-8-sig") as fp:
        w=csv.DictWriter(fp,fieldnames=fields);w.writeheader()
        for i in range(302):
            w.writerow(original(ident=str(i),status="VERIFIED_FULL" if i<45 else "PARTIAL_ORIGINAL"))
    return path


def test_frozen_originals_must_have_45_hash_exact_and_not_other_257(tmp_path):
    docs=s6.read_frozen(make_sample(tmp_path))
    assert len(docs)==45
    assert len({r["document_id"] for r in docs})==45
    assert all(r["pilot_status"]=="VERIFIED_FULL" for r in docs)
    assert all(r["body_sha256"]=="a"*64 for r in docs)


def test_reject_missing_one_verified_original(tmp_path):
    path=make_sample(tmp_path)
    lines=path.read_text(encoding="utf-8-sig").splitlines()
    with path.open("w",encoding="utf-8-sig") as f:
        f.write(lines[0]+"\n"+lines[1].replace("VERIFIED_FULL","PARTIAL_ORIGINAL")+"\n"+"\n".join(lines[2:])+"\n")
    with pytest.raises(ValueError,match="VERIFIED_FULL_45_EXPECTED"):
        s6.read_frozen(path)


def test_any_modified_body_hash_prevents_graph_reuse(monkeypatch):
    html="<html><body><article><p>Orders for solid rocket motors increased by 90 units.</p></article></body></html>"
    content=extract_document(html)["body"]
    assert content
    monkeypatch.setattr(s6,"fetch_capture",lambda url:{
        "html":html,"raw":html.encode(),"final_url":url,"status":200,
        "content_type":"text/html","truncated":False
    })
    monkeypatch.setattr(s6.target_acquisition,"verify",
                        lambda *a,**kw:pytest.fail("changed body must not enter provenance checks"))
    row=original(body_sha="b"*64)
    receipt,doc=s6.fetch_one(row,{"example.org":threading.Lock()})
    assert receipt["reaccess"]=="SOURCE_VERSION_CHANGED"
    assert receipt["first_blocker"]=="BODY_HASH_DIFFERS_FROM_SESSION5_SNAPSHOT"
    assert doc is None


def test_no_publisher_article_may_become_issuer_original_without_relation(monkeypatch):
    html="<article><p>Orders for gas turbines increased to 120 units.</p></article>"
    content=extract_document(html)["body"];digest=sha256(content.encode()).hexdigest()
    monkeypatch.setattr(s6,"fetch_capture",lambda url:{
       "html":html,"raw":html.encode(),"final_url":url,"status":200,
       "content_type":"text/html","truncated":False})
    proof={"provenance_verified":True,"provenance":"PASS","body_sha256":digest,
           "version":digest,"body":content,"published_at":"2026-11-01T00:00:00+00:00",
           "acquired_at":"2026-11-13T00:00:00+00:00",
           "origin_url":"https://example.org/item","origin_id":"example",
           "origin_publisher":"Example News","raw_sha256":sha256(html.encode()).hexdigest(),
           "publication_precision":"TIMESTAMP","checks":{"http_success":True}}
    monkeypatch.setattr(s6.target_acquisition,"verify",lambda *a,**kw:proof)
    monkeypatch.setattr(s6.precursor_collection,"structure",lambda d,raw,fresh: {**d,
                "precursor_events":[]})
    monkeypatch.setattr(s6.primary,"primary_origin",lambda d,events:False)
    receipt,doc=s6.fetch_one(original(body_sha=digest),
                {"example.org":threading.Lock()})
    assert receipt["source_version_same"]
    assert receipt["status"]=="SAME_VERSION_DOCUMENT_READ"
    assert receipt["issuer_primary_verified"] is False
    assert receipt["first_blocker"]=="PUBLISHER_SOURCE_NOT_ISSUER_PRIMARY"
    assert doc["provenance"]=="PASS"
    assert "body" not in receipt


def test_explicitly_unverified_provenance_never_enters_graph(monkeypatch):
    html="<article><p>Orders for gas turbines increased to 120 units.</p></article>"
    digest=sha256(extract_document(html)["body"].encode()).hexdigest()
    monkeypatch.setattr(s6,"fetch_capture",lambda url:{
       "html":html,"raw":html.encode(),"final_url":url,"status":200,
       "content_type":"text/html","truncated":False})
    monkeypatch.setattr(s6.target_acquisition,"verify",lambda *a,**kw:{
        "provenance_verified":False,"body_sha256":digest})
    receipt,doc=s6.fetch_one(original(body_sha=digest),
             {"example.org":threading.Lock()})
    assert receipt["reaccess"]=="PROVENANCE_CHANGED" and doc is None


def test_completely_missing_body_does_not_make_a_false_independent_pair():
    r=s6.graph_safe_summary([])
    assert r["independent_demand_supply_pairs"]==0
    assert r["backfill_protected_candidates"]==0
    assert r["graph_status"]=="NO_IMMUTABLE_VERIFIED_BODY_SNAPSHOT"


def test_whole_corpus_no_verifiable_body_still_visits_exact_45():
    rows=[original(ident=str(i)) for i in range(45)]
    calls=[]
    def fake_fetch(row,locks):
        calls.append(row["document_id"])
        return {**s6.result_stub(row),"reaccess":"PROVENANCE_CHANGED",
                "first_blocker":"SOURCE_UNVERIFIED"},None
    report,statuses,pairs=s6.run(rows,fetch_fn=fake_fetch)
    assert len(calls)==len(set(calls))==45
    assert report["reaccess_attempted"]==45
    assert report["eligible_verified_bottlenecks"]==0
    assert report["independent_demand_supply_pairs"]==0
    assert report["S1_S2_S3_new"]==0
    assert pairs==[]


def test_existing_graph_positive_fixture_is_research_backfill_not_forecast_s3():
    from test_precursor_evidence_graph import pair
    b,s=pair()
    r=s6.graph_safe_summary([b,s],now="2026-10-08T17:30:00+00:00")
    assert r["graph_status"]=="PASS_EXISTING_GRAPH_BACKFILL"
    assert r["independent_demand_supply_pairs"]==1
    assert r["comparable_period_pairs"]==1
    assert len(r["pairs"])==1
    assert r["pairs"][0]["forecast_confirmed"] is False
    assert r["pairs"][0]["reason"]=="BACKFILL_SCREENING_ONLY"
    assert r["backfill_protected_candidates"]==1
    assert r["protected_forecast_status"] in ("BLOCKED","UNVERIFIED")


def test_conflicting_product_contract_cannot_connect():
    from test_precursor_evidence_graph import pair
    from bct import precursor_collection as c
    from test_precursor_source_pipeline import doc
    b,s=pair()
    other=c.structure(doc("Firm new orders for nickel in Europe under contract K-543; required in 2028.",
                          "Other",url="https://other.example/news"))
    r=s6.graph_safe_summary([b,s,other],now="2026-10-08T17:30:00+00:00")
    assert r["independent_demand_supply_pairs"]==1
    assert len(r["pairs"])==1


def test_exported_cells_never_run_formula():
    assert s6.safe_csv("=IMPORTRANGE(...)").startswith("'")
    assert s6.safe_csv("https://example.org/a")=="https://example.org/a"
