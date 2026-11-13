"""Persisted acquisition evidence enters only conservative original-source lane."""
import copy,hashlib,sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from v4_precursor_original_research import validate


def fixture():
    url="https://electrek.co/2026/11/13/electric-trucks-update/"
    body="a"*64
    sector="자동차·배터리"
    key=hashlib.sha256(("\0".join((url,body,sector))).encode()).hexdigest()
    rec={"id":key,"source_document_id":"d"*64,
       "industry":sector,"title":"Electric trucks news","url":url,
       "origin_publisher":"Electrek","published_at":"2026-11-13T15:34:20+00:00",
       "collected_at":"2026-11-13T15:50:00+00:00",
       "body_sha256":body,"raw_sha256":"b"*64,
       "source_run_id":43473259686,"source_rss_run_id":43472909460,
       "source_manifest_sha256":"c"*64,
       "roles":["DEPLOYMENT"],"claim_offsets":[{"start":15,"end":21}],
       "product_names":["trucks"],"category":"rss_source_observation",
       "verification":"ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED",
       "confirmed_future_shortage":False,
       "independent_supply_demand_pair_verified":False}
    doc={"format":"bct-public-original-source-research-1",
         "classification":"SOURCE_VERIFIED_NOT_VERIFIED_SHORTAGE",
         "source_run_ids":[43473259686],
         "source_archive":{"run_id":43473259686,"rss_run_id":43472909460,
                           "bundle_manifest_sha256":"c"*64},
         "records":{key:rec},
         "verified_original_record_count":1}
    return doc,key


def test_source_bound_product_receipt_projects_without_bottleneck_promotion():
    data,key=fixture()
    obj=validate(data,data_commit="e"*40,rss_run_id=43472909460)
    assert obj["status"]=="VERIFIED_PERSISTED_ORIGINAL_SOURCE_RESEARCH"
    assert obj["verified_original_record_count"]==1
    assert obj["records"][0]["id"]==key
    assert obj["records"][0]["industry"]=="자동차·배터리"
    assert obj["records"][0]["confirmed_future_shortage"] is False
    assert "raw_html" not in obj["records"][0] and "body" not in obj["records"][0]


@pytest.mark.parametrize("field,value",[
  ("url","http://electrek.co/article"),
  ("origin_publisher","UNKNOWN"),
  ("body_sha256","0"*64),
  ("industry","전력·발전"),
  ("product_names",["battery"]),
  ("verification","UNVERIFIED"),
  ("confirmed_future_shortage",True),
  ("independent_supply_demand_pair_verified",True),
  ("source_run_id",43473259688),
  ("source_manifest_sha256","0"*64),
  ("published_at","UNKNOWN"),
  ("claim_offsets",[{"start":50,"end":10}]),
  ("roles",["guess"]),
])
def test_source_ledger_tampering_fails_closed(field,value):
    data,key=fixture()
    data["records"][key][field]=value
    with pytest.raises(ValueError):
        validate(data,data_commit="e"*40,rss_run_id=43472909460)


def test_data_ref_and_run_lineage_are_required():
    d,_=fixture()
    with pytest.raises(ValueError):
        validate(d,data_commit="not-sha",rss_run_id=43472909460)
    with pytest.raises(ValueError):
        validate(d,data_commit="e"*40,rss_run_id=43472909459)
    d["verified_original_record_count"]=2
    with pytest.raises(ValueError):
        validate(d,data_commit="e"*40,rss_run_id=43472909460)


def test_legacy_sector_research_stays_independent_from_new_immutable_register():
    exporter=(ROOT/"tools/v4_dashboard_static_export.py").read_text()
    checker=(ROOT/"tools/v4_dashboard_static_check.py").read_text()
    assert 'data["sector_rankings"] = ranks(data["records"])' in exporter
    assert 'data["registered_precursor_original_research"] = precursor_registered' in exporter
    assert 'data["rss_research_evidence"] = live_evidence' in exporter
    assert 'data["sector_rankings_live"]={' in exporter
    assert 'registered_source_research_sha256' in checker
    assert 'not r["confirmed_future_shortage"]' in checker
