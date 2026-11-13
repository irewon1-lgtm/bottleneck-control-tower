"""S6: media publisher self-identification is not official capacity evidence."""
from tools import bct_session6_source_role_correction as s6
import pytest

def fixtures():
    hosts=["electrek.co","theloadstar.com","www.biospace.com",
           "www.freightwaves.com","www.servethehome.com",
           "www.powermag.com","www.defensenews.com",
           "breakingdefense.com","9to5toys.com",
           "www.autoevolution.com","www.northernminer.com"]
    rows=[]
    for i in range(45):
        status=("PASS_SAME_VERIFIED_BODY_VERSION" if i<35
                else "SOURCE_VERSION_CHANGED" if i<44 else "NO_CURRENT_FULL_BODY")
        host=hosts[i%len(hosts)]
        rows.append({
           "document_id":str(i),"source_url":f"https://{host}/news/{i}",
           "source_host":host,
           "reaccess":status,
           "source_version_same":"True" if i<35 else "False",
           "issuer_primary_verified":"True" if i<4 else "False",
           "readable_event_count":94 if i==0 else 0,
           "demand_events":43 if i==0 else 0,
           "supply_events":51 if i==0 else 0,
           "scope_complete_events":0,"qualified_supplier_events":0,
           "explicit_future_need_events":1 if i==0 else 0,
           "body_sha256":"f"*64
        })
    report={
        "format":"bct-session6-cross-sector-original-source-audit-v1",
        "previous_verified_full":45,"reaccess_attempted":45,
        "current_same_hash_verified":35,"independent_demand_supply_pairs":0,
        "eligible_verified_bottlenecks":0,"issuer_primary_verified":4,
        "existing_graph":{"independent_demand_supply_pairs":0,
            "complete_target_events":0,"graph_observations":1502,
            "source_reference_checks":2248,"graph_edges":1}
    }
    return report,rows


def test_news_self_reference_flags_are_not_issuer_first_party():
    report,rows=fixtures()
    result,updated=s6.reconcile(report,rows)
    assert result["status"]=="PASS_CONSERVATIVE_RECLASSIFICATION"
    assert result["identical_body_and_publisher_verified"]==35
    assert result["primary_origin_heuristic_positives_not_independent_issuer_sources"]==4
    assert result["primary_issuer_source_verified"]==0
    assert result["independent_demand_supply_pairs"]==0
    assert result["S1_S2_S3_promotions"]==0
    assert all(r["issuer_primary_evidence_status"]=="NOT_VERIFIED_PRIMARY_ISSUER" for r in updated)
    assert result["semantic_leads_not_proof"]["demand_events"]==43
    assert result["semantic_leads_not_proof"]["supply_events"]==51


def test_duplicate_articles_fail_closed():
    r,rows=fixtures()
    rows[1]["document_id"]=rows[0]["document_id"]
    with pytest.raises(ValueError,match="INCOMPLETE"):
        s6.reconcile(r,rows)


def test_changed_original_identifier_is_blocked():
    r,rows=fixtures()
    rows[4]["source_url"]="https://different.example.com/foo"
    with pytest.raises(ValueError,match="SOURCE_IDENTITY_CHANGED"):
        s6.reconcile(r,rows)


def test_unreviewed_media_issuer_never_assumed_company_original():
    r,rows=fixtures()
    rows[0]["source_host"]="private-corporation.example"
    rows[0]["source_url"]="https://private-corporation.example/news/0"
    with pytest.raises(ValueError,match="REQUIRES_INDEPENDENT_REVIEW"):
        s6.reconcile(r,rows)


def test_unchanged_publisher_source_does_not_elevate_supply_capacity():
    report,rows=fixtures()
    _,updated=s6.reconcile(report,rows)
    assert all(r["firm_qualified_capacity_verified"]=="False" for r in updated)
    assert all(r["independent_pair_verified"]=="False" for r in updated)
    assert all(r["S1_S2_S3_new"]=="False" for r in updated)


def test_retained_reference_counts_cannot_be_silently_modified():
    r,rows=fixtures()
    r["existing_graph"]["source_reference_checks"]=2222
    with pytest.raises(ValueError,match="GRAPH_RECEIPT_CHANGED"):
        s6.reconcile(r,rows)


def test_unchanged_35_must_not_be_resampled_when_verification_failed():
    r,rows=fixtures()
    rows[0]["source_version_same"]="False"
    with pytest.raises(ValueError,match="SOURCE_VERSION_STATUS_INCONSISTENT"):
        s6.reconcile(r,rows)
