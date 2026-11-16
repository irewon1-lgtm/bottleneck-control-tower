"""BCT Session 7 truthful source-bound dashboard staging readout.

Read two actual, independent, read-only and tamper-checked source-free SQLite
receipts: durable S6 research branch and historical published Pages 511 proof.
Generate no ranking score, recommendation, qualified demand/supply pair or LIVE
candidate. The current time of rendering is NOT an evidence publication time.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

from bct.objective_lock import require_objective,stamp_export
from bct_s6_durable_sourcefree_research import readback as durable_readback
from bct_s6_pages_511_audit import requery as historical_readback

FORMAT="bct-s7-source-truth-preview-v1"
RESEARCH_BRANCH="research/bct-s6-sourcefree-ledger-20261116"
KNOWN_RESEARCH_DB_SHA="d0bef9da83910bf4ede638cea87df8f582bcb0cbb12033aee09aac64e832872d"
HISTORICAL_DATE="2026-10-14T23:16:13.592709+00:00"
ORIGINAL_PAGES_ARTIFACT_ID=14211394848
ORIGINAL_PAGES_ARTIFACT_DIGEST="sha256:641cf9c02359db448a34e02f35e9a58b1d72453ee4be8514b053e39a25368316"
PAGES_PROOF_RUN=43847161947
PAGES_PROOF_ARTIFACT=14215199098
PAGES_PROOF_ARTIFACT_DIGEST="sha256:2863a94473868f74b0cef0cb78e915b0c84eff3611a2cb320f6960abbf22b83d"
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
COUNT={"article_intake":316,"source_reentry_plan":60,"source_attempts":60,
       "target_holds":22,"research_facts":20,"source_bound_hints":147}

def canon(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False)

def sha(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()

def require(ok,code):
    if not ok:raise ValueError("BCT_S7_SOURCE_TRUTH_"+code)

def parse_time(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    require(dt.tzinfo is not None,"NAIVE_TIME")
    return dt.astimezone(timezone.utc)

def validate_inputs(research,history):
    s6=durable_readback(research)
    h6=historical_readback(history)
    report=json.loads((Path(research)/"research-summary.json").read_text())
    pages=json.loads((Path(history)/"published-511-reconciliation.json").read_text())
    require_objective(report);require_objective(pages)
    require(report.get("format")=="bct-s6-durable-sourcefree-research-ledger-v1"
          and report.get("sqlite_sha256")==KNOWN_RESEARCH_DB_SHA
          and report.get("source_counts")==COUNT
          and report.get("source_attempt_states")=={"FULL":24,"PARTIAL":22,"UNAVAILABLE":14}
          and report.get("source_original_verified")==18
          and report.get("registered_targets_preserved_hold")==22
          and report.get("strict_eligible_independent_pairs_admitted")==0
          and report.get("previous_public_rank_511")=="HISTORICAL_NOT_UPDATED"
          and report.get("data_or_future_branch_writes")==report.get("LIVE_writes")==
              report.get("public_Pages_deploys")==0,
          "RESEARCH_PROVENANCE_OR_HOLD_CONTRACT_CHANGED")
    require(s6["status"]=="PASS_DURABLE_S6_RESEARCH_SQLITE_FRESH_READBACK"
          and s6["articles"]==316 and s6["source_attempts"]==60
          and s6["verified_public_originals"]==18
          and s6["source_bound_hints"]==147 and s6["research_fact_codes"]==20
          and s6["HOLD_targets"]==22 and s6["qualified_pairs"]==0,
          "REAL_RESEARCH_DB_FRESH_READBACK_NOT_AUTHORIZED")
    require(pages.get("format")=="bct-s6-pages-511-rootcause-v1"
          and pages.get("source_run_id")==43838794301
          and pages.get("source_artifact_id")==ORIGINAL_PAGES_ARTIFACT_ID
          and pages.get("source_artifact_digest")==ORIGINAL_PAGES_ARTIFACT_DIGEST
          and pages.get("historical_rank_input_last_updated_at")==HISTORICAL_DATE
          and pages.get("historical_dashboard_record_count")==511
          and pages.get("historical_evidence_breakdown")=={
            "reviewed":23,"structured":211,"discovery":277}
          and pages.get("historical_ranked_sector_rows")==508
          and pages.get("historical_unclassified_records")==3
          and pages.get("published_detailed_evidence_files")==1703
          and pages.get("latest_rss_article_count_in_published_build")==10992
          and pages.get("live_overlay_new_publisher_verified_unpaired")==12
          and pages.get("historical_rank_input_not_increased_by_RSS") is True
          and pages.get("automatically_promoted_shortage_candidates")==0,
          "HISTORICAL_PUBLISHED_SITE_NOT_SAME_VERIFIED_RECEIPT")
    require(h6["status"]=="PASS_PUBLIC_511_SQLITE_FRESH_REQUERY"
          and h6["historical_records"]==511 and h6["detail_files"]==1703
          and h6["live_overlay"]==520,
          "HISTORICAL_SQLITE_REQUERY_NOT_VALID")
    return report,pages

def compile_status(research_dir,history_dir,*,research_sha,main_sha,sidecar_sha,data_sha,
                   now=None):
    for candidate in (research_sha,main_sha,sidecar_sha,data_sha):
        require(isinstance(candidate,str) and SHA40.fullmatch(candidate),
                "UNPINNED_GITHUB_COMMIT_REF")
    report,pages=validate_inputs(research_dir,history_dir)
    checked=parse_time(now) if isinstance(now,str) else (
        datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc))
    require(checked.tzinfo is not None,"UTC_TIME_REQUIRED")
    source_counts=report["source_counts"]
    return stamp_export({
        "format":FORMAT,
        "status":"PASS_RESEARCH_SOURCEBOUND_PRESENTATION_PREVIEW_ONLY",
        "view":"S7_PROOF_NOT_PUBLIC_OPERATING_PAGES",
        "checked_at_utc":checked.isoformat(),
        "research":{"status":"VERIFIED_S6_ISOLATED_SOURCE_FREE_HOLD",
          "branch":RESEARCH_BRANCH,
          "commit_sha":research_sha,
          "sqlite_sha256":report["sqlite_sha256"],
          "rss_only_article_ids":source_counts["article_intake"],
          "article_reentry_attempts":source_counts["source_attempts"],
          "body_states":dict(report["source_attempt_states"]),
          "strict_original_publisher_body_date_verified":report["source_original_verified"],
          "registered_target_holds":source_counts["target_holds"],
          "official_public_fact_codes_research_only":source_counts["research_facts"],
          "new_sourcebound_research_hints_not_independent_pairs":source_counts["source_bound_hints"],
          "not_attempted_in_316_snapshot":316-60,
          "admitted_qualified_independent_pairs":0,
          "research_fact_units_not_additive_to_historical_count":True,
          "stage6_status":"PARTIAL"
        },
        "historical":{"status":"FROZEN_2026_10_14_NOT_FRESH_EVIDENCE",
          "data_at_utc":HISTORICAL_DATE,
          "record_count":pages["historical_dashboard_record_count"],
          "counts":dict(pages["historical_evidence_breakdown"]),
          "sector_ranked_records":pages["historical_ranked_sector_rows"],
          "unclassified_records":pages["historical_unclassified_records"],
          "published_detail_files_different_units":1703,
          "same_published_build_rss_article_count":10992,
          "overlay_new_originals_unpaired":pages["live_overlay_new_publisher_verified_unpaired"],
          "original_pages_artifact_id":ORIGINAL_PAGES_ARTIFACT_ID,
          "original_pages_digest":ORIGINAL_PAGES_ARTIFACT_DIGEST,
          "pages_proof_run":PAGES_PROOF_RUN,
          "pages_proof_artifact":PAGES_PROOF_ARTIFACT,
          "rank_is_current_verifiable_shortage":False
        },
        "generations":{"main_code_commit":main_sha,"rss_data_commit_observed":data_sha,
                       "sidecar_commit_observed":sidecar_sha,
                       "research_ledger_commit":research_sha,
                       "observed_operating_heads_are_not_evidence_time":True},
        "admission":{"eligible_independent_pair_count":0,
                     "strict_pair_evaluation_for_all_corpus":"NOT_PERFORMED",
                     "forecast_accuracy":"UNVERIFIED",
                     "historical_rank_511_not_updated":True,
                     "new_research_hints_not_ranked":True},
        "deployment":{"public_pages_deployed_by_this_job":False,
                      "operating_rss_or_sidecar_writes":0,"LIVE_writes":0,
                      "public_rank_writes":0,
                      "session7":"SOURCE_TRUTH_PREVIEW_NOT_PUBLIC_DEPLOYMENT",
                      "session8":"NOT_RUN"},
        "provenance":{
          "source_branch_record_verified_sha256":report["sqlite_sha256"],
          "historical_published_receipt_verified_sha256":pages["sqlite_sha256"],
          "readback_method":"TWO_INDEPENDENT_IMMUTABLE_SOURCE_FREE_SQLITES",
          "rank_count_source":"PUBLISHED_PAGES_HISTORICAL_DATA_ONLY",
          "research_count_source":"PERSISTED_GIT_RESEARCH_SQLITE_ONLY"
        }
    })

def save_status(status,output):
    output=Path(output)
    require(not output.exists(),"OUTPUT_OVERWRITE_FORBIDDEN")
    output.parent.mkdir(parents=True,exist_ok=True)
    require(status["format"]==FORMAT
            and status["research"]["admitted_qualified_independent_pairs"]==0
            and status["admission"]["eligible_independent_pair_count"]==0
            and status["historical"]["record_count"]==sum(status["historical"]["counts"].values())
            and status["deployment"]["public_pages_deployed_by_this_job"] is False,
            "UNAUTHORIZED_STAGING_SUMMARY")
    output.write_text(canon(status)+"\n",encoding="utf-8")
    again=json.loads(output.read_text())
    require_objective(again)
    require(again==status,"STAGING_STATUS_JSON_REQUERY_CHANGED")
    return {
        "status":"PASS_S7_SOURCE_STATUS_JSON_FRESH_REQUERY",
        "sha256":sha(output.read_bytes()),
        "historical_511":again["historical"]["record_count"],
        "new_research_hints":again["research"]["new_sourcebound_research_hints_not_independent_pairs"],
        "originals_strict":again["research"]["strict_original_publisher_body_date_verified"],
        "admitted_physical_pairs":again["admission"]["eligible_independent_pair_count"],
        "public_deployed":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--research",type=Path,required=True)
    p.add_argument("--pages-proof",type=Path,required=True)
    p.add_argument("--research-sha",required=True)
    p.add_argument("--main-sha",required=True)
    p.add_argument("--sidecar-sha",required=True)
    p.add_argument("--data-sha",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    status=compile_status(args.research,args.pages_proof,
                          research_sha=args.research_sha,
                          main_sha=args.main_sha,
                          sidecar_sha=args.sidecar_sha,
                          data_sha=args.data_sha)
    proof=save_status(status,args.out)
    print("BCT_S7_SOURCE_BOUND_DASHBOARD_PREVIEW="+canon(proof),flush=True)

if __name__=="__main__":
    main()
