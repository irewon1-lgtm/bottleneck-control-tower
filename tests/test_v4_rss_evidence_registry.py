"""No unchecked RSS headline or preliminary fact enters V4 ranked evidence."""
import hashlib
from pathlib import Path
import re
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from v4_rss_evidence_registry import register

SHA="a"*64
URL="https://example.org/real/lithium-report"

def record(*,verified=True,publication=True,target="lithium",body_status="FULL",id_suffix="1",
           original_url=URL,actual=True,role="SUPPLY"):
    metadata={
        "origin_id":original_url,"origin_url":original_url,
        "origin_publisher":"Example Minerals",
        "provenance_verified":verified,
        "provenance_evidence":{"body_sha256":SHA,"verified_source_url":original_url,
                               "source_identity":"original verified canonical"},
        "published_at":"2026-11-13","publication_precision":"DATE",
        "publication_verified":publication,
        "publication_evidence":{"body_sha256":SHA,"source_quote":"2026-11-13"},
    }
    return {
        "id":"article-"+id_suffix,
        "url":original_url,"title":"Lithium mineral mining capacity increases",
        "collected_at":"2026-11-14T00:00:00+00:00",
        "candidate":True,"current_body_sha256":SHA,"body_sha256":SHA,
        "body_status":body_status,"body_chars":300,
        "versions":{SHA:{"body_status":body_status,"body_chars":300,**metadata}},
        "scope_facts":[{"role":role,"target":target,"locator":{"start":10,"end":90},
                        "actual_statement":actual,"scope_ambiguous":False}]
    }


def register_rows(items):
    return register({"results":items},sidecar_sha="b"*40,feed_domains={"example.org":"광물·희토류"})


def test_verifiable_original_literal_product_registers_exactly_once():
    results=register_rows({"a":record(),"b":record(id_suffix="2")})
    assert results["source_verified_sector_count"]==1
    assert results["counts"]["deduplicated_exact_origin_body_sector"]==1
    x=results["source_records"][0]
    assert x["industry"]=="광물·금속·희토류"
    assert x["url"]==URL and x["confirmed_future_shortage"] is False
    assert x["category"]=="rss_source_observation"
    assert x["roles"]==["SUPPLY"]
    assert x["claim_offsets"]==[{"start":10,"end":90}]


@pytest.mark.parametrize("change",[
    {"verified":False},{"publication":False},{"body_status":"PARTIAL"},
    {"target":"UNKNOWN"},{"actual":False},{"role":"CHANGE"},
    {"original_url":"https://unrelated.example/lithium"},
])
def test_unverified_screening_lead_never_increases_rank(change):
    a=record(**change)
    results=register_rows({"a":a})
    if change=={"original_url":"https://unrelated.example/lithium"}:
        assert results["source_verified_sector_count"]==1
    else:
        assert results["source_verified_sector_count"]==0


def test_feed_hint_does_not_establish_a_product_sector():
    value=register_rows({"a":record(target="UNKNOWN")})
    assert value["source_verified_sector_count"]==0
    assert value["groups"]["광물·금속·희토류"]["source_located_leads"]==1
    assert value["counts"]["verified_original_needing_product_sector_review"]==1


def test_multiple_product_sectors_in_single_fact_cannot_be_certified():
    value=register_rows({"a":record(target="lithium rocket motors")})
    assert value["source_verified_sector_count"]==0


def test_invalid_claim_offset_must_be_held():
    a=record()
    a["scope_facts"][0]["locator"]["end"]=999
    value=register_rows({"a":a})
    assert value["source_verified_sector_count"]==0


def test_tampered_original_source_body_binding_rejected():
    a=record()
    a["versions"][SHA]["provenance_evidence"]["body_sha256"]="0"*64
    value=register_rows({"a":a})
    assert value["source_verified_sector_count"]==0


def test_never_publishes_article_body_or_invents_independent_pairs():
    result=register_rows({"a":record()})
    row=result["source_records"][0]
    assert "body" not in row and "source_quote" not in row
    assert row["verification"]=="ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED"
    assert not row["confirmed_future_shortage"]


def test_reverified_existing_full_body_can_be_registered_without_rewriting_immutable_version():
    old=record()
    sha=old["current_body_sha256"]
    proof=dict(old["versions"][sha])
    old["versions"][sha]={"body_status":"FULL","body_chars":300,
        "scope_facts":old["scope_facts"],"provenance_verified":False}
    old.update(proof)
    found=register_rows({"old-original-reverified":old})
    assert found["source_verified_sector_count"]==1
    assert found["counts"]["verified_original_and_publication"]==1
    # A changed body hash invalidates all old issuer claims before reranking.
    old["current_body_sha256"]="0"*64
    assert register_rows({"changed-with-old-publisher-proof":old})["source_verified_sector_count"]==0


def test_real_source_wording_own_battery_cells_maps_to_explicit_battery_sector():
    # A real source-verified Tesla battery-cell issuer statement was held only
    # because the old taxonomy demanded the exact EV prefix. Cells are a
    # physical battery product, not a proof of a future shortage.
    row=record(target="its own battery cells",role="SUPPLY")
    result=register_rows({"source-original":row})
    assert result["source_verified_sector_count"]==1
    assert result["source_records"][0]["industry"]=="자동차·배터리"
    assert result["source_records"][0]["confirmed_future_shortage"] is False


def test_battery_cell_software_mentions_remain_outside_literal_product_match():
    result=register_rows({"nonphysical":record(target="battery management algorithms",role="DEMAND")})
    assert result["source_verified_sector_count"]==0


def test_composite_lithium_battery_target_remains_multisector_pending():
    # A mineral plus a finished battery component is not silently assigned
    # to one sector without an explicit relationship or independently
    # confirmed product scope.
    result=register_rows({"mixed":record(target="lithium battery cells",role="SUPPLY")})
    assert result["source_verified_sector_count"]==0
