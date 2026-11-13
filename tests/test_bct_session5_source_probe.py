"""Session5 new blinded-source probe: no publisher text or unverifiable stages."""
import csv
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


def mod():
    spec=importlib.util.spec_from_file_location(
        "session5_probe",ROOT/"tools/bct_session5_source_probe.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def record(i):
    return {"document_id":f"doc{i:03d}","source":"site.example",
            "url":f"https://site.example/story/{i:03d}","title":f"Article {i}",
            "published_at":"2026-11-12T00:00:00Z",
            "DEMAND_label":"UNKNOWN","SUPPLY_label":"UNKNOWN","RELIEF_label":"UNKNOWN"}


def create_packets(path,*,wrong_label=False):
    one=[record(i) for i in range(240)]
    two=[record(i) for i in range(239,302)]
    if wrong_label:two[0]["SUPPLY_label"]="TRUE"
    cols=list(one[0])
    for name,data in (("blind_reference_packet_240.csv",one),
                      ("blind_new_P1_packet.csv",two)):
        with (path/name).open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(data)


def test_read_two_packets_retains_302_unique_only(tmp_path):
    create_packets(tmp_path)
    p=mod()
    rows=p.read_packets(tmp_path)
    assert len(rows)==302 and len(set(r["document_id"] for r in rows))==302
    assert all(r["DEMAND_label"]=="UNKNOWN" for r in rows)


def test_fake_positive_label_is_not_allowed_into_blind_packet(tmp_path):
    create_packets(tmp_path,wrong_label=True)
    with pytest.raises(ValueError,match="BLIND_INPUT_UNVERIFIED"):
        mod().read_packets(tmp_path)


def test_original_captured_without_provenance_stays_research_hold(monkeypatch):
    p=mod()
    def capture(url):
        raw=b'<html><body><article><p>Orders for gas turbines increased to 120 units in 2028.</p></article></body></html>'
        return {"html":raw.decode(),"raw":raw,"final_url":url,
                "status":200,"content_type":"text/html","truncated":False}
    monkeypatch.setattr(p,"fetch_capture",capture)
    monkeypatch.setattr(p,"verify",lambda *a,**kw:{
        "provenance_verified":False,"provenance_blockers":["ORIGINAL_IDENTITY"]})
    import threading
    result=p.one_source(record(0),{"site.example":threading.Lock()})
    assert result["pilot_status"]=="FULL_UNVERIFIED_ORIGINAL"
    assert result["body_status"]=="FULL"
    assert result["demand_leads"]>=1
    assert not result["S1_S2_S3"]
    assert result["labels"]=="UNKNOWN"
    assert "body" not in result


def test_verified_full_only_after_complete_source_identity(monkeypatch):
    p=mod()
    def capture(url):
        raw=b'<html><body><article><p>Production of solid rocket motors was halted.</p></article></body></html>'
        return {"html":raw.decode(),"raw":raw,"final_url":url,
                "status":200,"content_type":"text/html","truncated":False}
    monkeypatch.setattr(p,"fetch_capture",capture)
    monkeypatch.setattr(p,"verify",lambda *a,**kw:{
        "provenance_verified":True,"provenance_blockers":[]})
    import threading
    value=p.one_source(record(0),{"site.example":threading.Lock()})
    assert value["pilot_status"]=="VERIFIED_FULL"
    assert value["supply_leads"]>=1 and not value["S1_S2_S3"]


def test_http_forbidden_is_not_retried_or_promoted(monkeypatch):
    from urllib.error import HTTPError
    p=mod();calls=[]
    def blocked(url):
        calls.append(url)
        raise HTTPError(url,403,"Forbidden",{},None)
    monkeypatch.setattr(p,"fetch_capture",blocked)
    import threading
    result=p.one_source(record(0),{"site.example":threading.Lock()})
    assert calls==[record(0)["url"]]
    assert result["pilot_status"]=="ACCESS_OR_EXTRACTION_ERROR"
    assert result["access_classification"]=="HTTP_403"
    assert not result["S1_S2_S3"]


def test_truncated_full_cannot_qualify_original(monkeypatch):
    p=mod()
    def capture(url):
        raw=b'<html><body><article><p>Orders for gas turbines increased to 120 units.</p></article></body></html>'
        return {"html":raw.decode(),"raw":raw,"final_url":url,
                "status":200,"content_type":"text/html","truncated":True}
    monkeypatch.setattr(p,"fetch_capture",capture)
    monkeypatch.setattr(p,"verify",lambda *a,**kw:{
        "provenance_verified":True,"provenance_blockers":[]})
    import threading
    record_out=p.one_source(record(0),{"site.example":threading.Lock()})
    assert record_out["pilot_status"]=="PARTIAL_ORIGINAL"
    assert not record_out["provenance_verified"]


def test_never_schedule_more_than_six_workers():
    with pytest.raises(ValueError,match="MAX_CONCURRENCY_6"):
        mod().run([],workers=7)
