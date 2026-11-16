"""S5 22-TARGET bounded disposition review and S6 research-only intake.

This audits ALL 22 identifiers in the preserved, immutable 2026-10-08 TARGET
inventory. It does NOT label historical FUTURE/EMERGING as strict passes or
infer full 10k+ RSS article coverage. It never edits canonical/LIVE/rank data.
"""
import argparse
from collections import Counter,defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from bct.objective_lock import stamp_export, require_objective

FORMAT="bct-s5-22-target-closed-disposition-v1"
HANDOFF_FORMAT="bct-s6-research-intake-pending-v1"
CUTOFF="2026-11-16"
S5_RUN=43824301850
S5_ARTIFACT=14205666980
S5_ARTIFACT_DIGEST="sha256:f077f746cb06ce5de6efe59b77882a6136b00c77d6b9cc9e3d697c35624110a7"
S5_SHA="24152347209ee696f1fb181d9a8b842dc0515496"
S5_EXPECTED="bct-s5-supplier-facts-readonly-v1"
QA_REL="docs/validation/precursor-evidence-graph-20261008/results.json"
LEGACY_REL="docs/verified-bottlenecks.json"
EXPECTED_TARGETS=22
BLOCKER="NO_INDEPENDENT_SAME_TARGET_ELIGIBLE_DEMAND_SUPPLY_AND_COMPARABLE_PERIOD"
REG_PATTERN=re.compile(r"2026\d{4}[-_].*\.json$")
HEX64=re.compile(r"^[0-9a-f]{64}$")

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

def digest(raw):
    if not isinstance(raw,bytes):raw=canonical(raw).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def require(ok,code):
    if not ok:raise ValueError("BCT_S5_BOUND_"+code)

def checked_source(root,rel):
    root=Path(root)
    p=root/rel
    require(p.resolve().is_relative_to(root.resolve()),"UNSAFE_SOURCE_PATH")
    raw=p.read_bytes()
    return json.loads(raw),digest(raw)

def validate_qa(q):
    tc=q.get("target_coverage")
    require(isinstance(tc,list) and len(tc)==EXPECTED_TARGETS,"FROZEN_TARGET_SET_NOT_22")
    ids=[]
    for x in tc:
        require(isinstance(x,dict) and isinstance(x.get("target_id"),str)
                and x["target_id"] and isinstance(x.get("target"),str)
                and x["target"] and type(x.get("verified_full_originals")) is int
                and x["verified_full_originals"]>=0
                and x.get("unresolved")==
                  "FULL_ORIGINAL_OR_EXPLICIT_CUSTOMER_QUALIFICATION_PERIOD_COVERAGE_REQUIRED",
                "TARGET_ORIGINAL_COVERAGE_PROOF_CHANGED")
        ids.append(x["target_id"])
    require(len(set(ids))==EXPECTED_TARGETS,"DUPLICATED_FROZEN_TARGET")
    original=q.get("registered_official",{})
    metrics=original.get("metrics",{})
    require(type(original.get("unique_verified_originals")) is int
            and original["unique_verified_originals"]>=0
            and metrics.get("independent_pairs")==0
            and metrics.get("complete_target_events")==0
            and metrics.get("backfill_early_candidates")==0,
            "HISTORICAL_ORIGINAL_EVIDENCE_PAIR_GATE_CHANGED")
    require(q.get("final_assessment",{}).get("real_independent_demand_supply_link")=="PARTIAL",
            "HISTORICAL_GRAPH_ASSESSMENT_CHANGED")
    return tc

def validate_s5(s5):
    require(s5.get("format")==S5_EXPECTED
            and s5.get("status")==
                "PASS_READONLY_SOURCE_BOUND_RISK_AND_NONPROMOTION_CLASSIFICATION"
            and s5.get("session5_final")==
                "PARTIAL_NO_SAME_PERIOD_ELIGIBLE_UNRESERVED_SUPPLY_EVIDENCE"
            and s5.get("public_source_bodies_captured")==3
            and s5.get("verified_visible_public_originals")==3
            and s5.get("verified_distinct_fact_count")==8
            and s5.get("centrus_same_disclosure_copies_not_independent_pair")==3
            and s5.get("strict_pair_evaluated") is False
            and s5.get("actual_qualified_pair_count")=="NOT_EVALUATED"
            and s5.get("new_bottleneck_candidates")==0
            and s5.get("model_API_calls")==s5.get("private_epoch_writes")==s5.get("LIVE_writes")==0
            and s5.get("original_source_text_stored") is False
            and s5.get("objective_version")=="bct-objective-1",
            "S5_ACTUAL_SUPPLIER_RECEIPT_NOT_ATTESTED")
    require_objective(s5)
    annual=s5.get("2027_2030_demonstrated_demand_minus_supply_MTU",{})
    require(set(annual)=={"2027","2028","2029","2030"}
            and set(annual.values())=={"UNKNOWN"},"ANNUAL_ELIGIBLE_SUPPLY_NOT_UNKNOWN")
    return s5

def discover_registered(root):
    """Only the fixed YYYYMMDD registration patch files; not arbitrary JSON."""
    root=Path(root)
    directory=root/"docs/registrations"
    files=sorted(x for x in directory.iterdir() if x.is_file() and REG_PATTERN.fullmatch(x.name))
    require(len(files)>=15,"REGISTRATION_HISTORY_NOT_PRESENT")
    groups=defaultdict(list)
    allfiles=[]
    for file in files:
        data,sha=checked_source(root,str(file.relative_to(root)))
        patch=data.get("patch",{})
        targets=patch.get("targets",[]) if isinstance(patch,dict) else []
        require(isinstance(targets,list),"HISTORICAL_PATCH_TARGETS_NOT_ARRAY")
        for target in targets:
            require(isinstance(target.get("id"),str) and target["id"],"REG_TARGET_ID_MISSING")
            hist=target.get("history")
            require(isinstance(hist,list) and hist,"REG_HISTORY_REQUIRED")
            for row in hist:
                require(isinstance(row,dict),"BAD_HISTORICAL_REVIEW")
                # Historical research judgments are not proof of an actual
                # independently qualified original-source pair.
                require(row.get("strict_pass_claim") is not True
                        and row.get("early_detection_claim") is not True,
                        "HISTORICAL_POSITIVE_CLAIM_REQUIRES_INDEPENDENT_REPROOF")
                groups[target["id"]].append({
                    "registration_sha256":sha,
                    "registration_path":str(file.relative_to(root)),
                    "history_id":row.get("review_id") or row.get("id"),
                    "history_status":row.get("status","UNKNOWN"),
                    "reported_at":row.get("recorded_at",row.get("reviewed_on")),
                    "strict_claim":row.get("strict_pass_claim","NOT_ASSERTED"),
                    "research_judgment":row.get("research_judgment","UNSPECIFIED")})
        allfiles.append({"path":str(file.relative_to(root)),
                         "sha256":sha,"target_rows":len(targets)})
    return groups,allfiles

def review(root,s5):
    root=Path(root)
    qa,qa_sha=checked_source(root,QA_REL)
    catalog=validate_qa(qa)
    legacy,legacy_sha=checked_source(root,LEGACY_REL)
    require(type(legacy.get("items")) is list,"BASELINE_LEGACY_NOT_PRESENT")
    prior={x["id"]:x.get("status","UNKNOWN") for x in legacy["items"]}
    require(len(prior)==len(legacy["items"]) and
            set(prior).issubset({x["target_id"] for x in catalog}),
            "UNRECONCILED_LEGACY_TARGET")
    groups,files=discover_registered(root)
    registered_ids={x["target_id"] for x in catalog}
    require(set(groups).issubset(registered_ids),
            "NEW_UNREVIEWED_TARGET_NOT_IN_FROZEN_COHORT")
    validate_s5(s5)
    cases=[]
    for x in catalog:
        tid=x["target_id"]
        prev=groups.get(tid,[])
        # A historical observation is always context, NEVER an automatic
        # verified qualifying pair. Absence of a pair is HOLD, not rejection.
        verified=x["verified_full_originals"]
        classification="HOLD"
        reason=("HOLD_ORIGINALS_EXIST_NO_INDEPENDENT_ELIGIBLE_PAIR" if verified
                else "HOLD_NO_VERIFIED_ORIGINAL_IN_FROZEN_QA")
        case={
            "case_id":digest(["bct-s5-target-review-v1",tid]),
            "target_id":tid,
            "research_disposition":classification,
            "decision_reason":reason,
            "must_not_discard_unproven_lead":True,
            "historical_original_documents_at_2026_10_08":verified,
            "historical_registration_review_count":len(prev),
            "historical_registration_file_sha256":sorted({z["registration_sha256"] for z in prev}),
            "historical_review_statuses":sorted({z["history_status"] for z in prev}),
            "prior_display_stage_2026_09_30":prior.get(tid,"NONE"),
            "is_legacy_stage_proof":False,
            "source_independent_pair_verified":False,
            "same_target_product_spec_region_customer_supply_pool_verified":False,
            "qualified_unreserved_same_period_supply_verified":False,
            "known_annual_deficit_measured":"UNKNOWN",
            "verified_falsifier_of_exact_target":False,
            "next_action":"S6_PRESERVE_HOLD_WITH_SOURCE_LINEAGE_NOT_RANK",
            "s5_new_research":"8_SOURCE_BOUND_FACTS_NO_ELIGIBLE_PAIR" if tid==
                "unobligated-haleu-us-qualified-supply" else "NO_NEW_VERIFIED_PAIR_AT_S5_CUTOFF"
        }
        cases.append(case)
    require(len(cases)==EXPECTED_TARGETS and
            len({c["case_id"] for c in cases})==EXPECTED_TARGETS,
            "NOT_ALL_22_CASES_EXAMINED")
    counts=Counter(c["research_disposition"] for c in cases)
    require(counts=={"HOLD":EXPECTED_TARGETS},"UNAUTHORIZED_QUALIFIED_OR_REJECTED_CASE")
    if any(c["source_independent_pair_verified"] or
           c["qualified_unreserved_same_period_supply_verified"] or
           c["verified_falsifier_of_exact_target"] for c in cases):
        raise ValueError("BCT_S5_BOUND_POSITIVE_OR_FALSIFIER_NEEDS_SOURCE_PAIR")
    summary=stamp_export({
        "format":FORMAT,"cutoff_date":CUTOFF,
        "scope":"EXACT_22_FROZEN_REGISTERED_TARGETS_NOT_FULL_RSS_CORPUS",
        "cohort_disposition":"PASS_ALL_22_TARGETS_EXPLICITLY_CATEGORIZED",
        "full_S5_market_forecast_verification":"PARTIAL_UNKNOWN_INDEPENDENT_ELIGIBLE_PAIR",
        "s6_handoff_status":"READY_RESEARCH_HOLD_ONLY_NOT_PRODUCTION_EVIDENCE_INTEGRATION",
        "targets_reviewed":EXPECTED_TARGETS,"targets_total":EXPECTED_TARGETS,
        "qualified":counts.get("QUALIFIED",0),
        "rejected":counts.get("REJECTED",0),
        "hold":counts.get("HOLD",0),
        "qa_original_documents_distinct_reported":
            qa["registered_official"]["unique_verified_originals"],
        "qa_target_original_count_is_not_distinct_document_total":True,
        "qa_catalog_sha256":qa_sha,
        "legacy_stage_catalog_sha256":legacy_sha,
        "legacy_prior_display_stages":dict(sorted(Counter(prior.values()).items())),
        "registration_files_read":len(files),
        "historical_registration_reviews_read":sum(len(z) for z in groups.values()),
        "registered_target_ids_with_history":len(groups),
        "original_target_ids_without_registration":EXPECTED_TARGETS-len(groups),
        "s5_supplier_receipt_run":S5_RUN,
        "s5_supplier_receipt_artifact":S5_ARTIFACT,
        "s5_supplier_receipt_expected_digest":S5_ARTIFACT_DIGEST,
        "s5_supplier_receipt_expected_head":S5_SHA,
        "s5_supplier_primary_originals_captured":s5["public_source_bodies_captured"],
        "s5_distinct_source_bound_facts":s5["verified_distinct_fact_count"],
        "s5_strict_pair_evaluated":False,
        "full_10k_article_research_audit":"NOT_PERFORMED",
        "previous_public_511_evidence_count":"NOT_REVALIDATED_DO_NOT_CARRY_FORWARD_AS_CURRENT",
        "LIVE_candidates_created":0,"production_research_DB_writes":0,
        "production_rank_writes":0,"private_source_writes":0,
        "next_stage_goal":"S6_COUNT_AND_JOIN_ONLY_VERIFIED_EVIDENCE_IDS_WITH_ACTUAL_RESEARCH_DB",
        "forecast_accuracy":"UNVERIFIED"})
    return summary,cases,files

def write_result(folder,summary,cases,files):
    p=Path(folder)
    require(not p.exists(),"OUTPUT_EXISTS")
    p.mkdir(parents=True)
    f=p/"s5-to-s6-research.sqlite3"
    with sqlite3.connect(f) as conn:
        conn.execute("CREATE TABLE cases (id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        conn.execute("CREATE TABLE provenance (path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,rows_count INTEGER NOT NULL)")
        for x in sorted(cases,key=lambda x:x["case_id"]):
            payload=canonical(x)
            conn.execute("INSERT INTO cases VALUES (?,?,?)",(x["case_id"],digest(payload.encode()),payload))
        for r in files:
            conn.execute("INSERT INTO provenance VALUES(?,?,?)",
                         (r["path"],r["sha256"],r["target_rows"]))
    result=dict(summary)
    result["sqlite_sha256"]=digest(f.read_bytes())
    result["cases_sha256"]=digest(canonical(sorted(cases,key=lambda x:x["case_id"])))
    result["provenance_count"]=len(files)
    (p/"s5-closed-review.json").write_text(canonical(result)+"\n")
    handoff=stamp_export({
        "format":HANDOFF_FORMAT,
        "S5_scoped_22_target_review":"PASS",
        "s6_intake_scope":"RESEARCH_ONLY_HOLD_22_NOT_PUBLIC_RANK",
        "parent_sha256":digest(canonical(result)),
        "source_sqlite_sha256":result["sqlite_sha256"],
        "source_cases_sha256":result["cases_sha256"],
        "eligible_to_integrate_verified_pairs":0,
        "hold_cases_for_research_DB":22,
        "original_511_public_evidence_count":"NOT_REVALIDATED",
        "promotion_allowed":False,
        "production_DB_write_allowed":False,
        "S6_full_database_integration":"NOT_RUN",
        "s6_next_action":"READ_ACTUAL_OPERATING_SIDE_CAR_EVIDENCE_IDS_AND_RECONCILE",
    })
    (p/"s6-research-handoff.json").write_text(canonical(handoff)+"\n")
    fresh_readback(p)
    return result,handoff

def fresh_readback(path):
    p=Path(path)
    report=json.loads((p/"s5-closed-review.json").read_text())
    handoff=json.loads((p/"s6-research-handoff.json").read_text())
    require_objective(report);require_objective(handoff)
    db=p/"s5-to-s6-research.sqlite3"
    require(digest(db.read_bytes())==report["sqlite_sha256"],"SQLITE_CHANGED")
    with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True) as conn:
        require(conn.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INTEGRITY")
        cases=conn.execute("SELECT id,payload_sha256,payload FROM cases ORDER BY id").fetchall()
        meta=conn.execute("SELECT path,sha256,rows_count FROM provenance ORDER BY path").fetchall()
    require(len(cases)==EXPECTED_TARGETS and len(meta)==report["provenance_count"],
            "REQUERY_COUNT_CHANGED")
    restored=[]
    for key,h,payload in cases:
        require(digest(payload.encode())==h,"REQUERY_RECORD_HASH")
        x=json.loads(payload)
        require(key==x["case_id"] and x["research_disposition"]=="HOLD"
                and x["known_annual_deficit_measured"]=="UNKNOWN",
                "INVALID_PROTECTED_DISPOSITION")
        restored.append(x)
    require(digest(canonical(restored))==report["cases_sha256"]
            and handoff.get("source_sqlite_sha256")==report["sqlite_sha256"]
            and handoff.get("source_cases_sha256")==report["cases_sha256"]
            and handoff.get("parent_sha256")==digest(canonical(report))
            and handoff.get("eligible_to_integrate_verified_pairs")==0
            and handoff.get("promotion_allowed") is False
            and handoff.get("S6_full_database_integration")=="NOT_RUN",
            "S6_HANDOFF_MISMATCH")
    return {
        "status":"PASS_FRESH_SOURCE_FREE_22_TARGETS_AND_S6_HOLD_HANDOFF",
        "cases":len(restored),"HOLD":len(restored),"QUALIFIED":0,"REJECTED":0,
        "sqlite_sha256":report["sqlite_sha256"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",type=Path,default=Path("."))
    parser.add_argument("--s5-source-receipt",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify-only",action="store_true")
    args=parser.parse_args()
    if args.verify_only:
        print("BCT_S5_S6_READBACK="+canonical(fresh_readback(args.out)))
        return
    require(args.s5_source_receipt is not None,"ORIGINAL_S5_RECEIPT_REQUIRED")
    s5=json.loads(args.s5_source_receipt.read_text())
    summary,cases,files=review(args.repo_root,s5)
    final,handoff=write_result(args.out,summary,cases,files)
    print("BCT_S5_FROZEN_TARGET_TRIAGE="+canonical({
       "status":final["cohort_disposition"],
       "target_count":final["targets_reviewed"],
       "qualified":final["qualified"],
       "rejected":final["rejected"],
       "hold":final["hold"],
       "historic_verified_origins":final["qa_original_documents_distinct_reported"],
       "registration_files":final["registration_files_read"],
       "historical_reviews":final["historical_registration_reviews_read"],
       "s6_handoff":final["s6_handoff_status"],
       "production_writes":final["production_research_DB_writes"],
       "full_corpus":final["full_10k_article_research_audit"],
       "forecast_accuracy":final["forecast_accuracy"]}))
if __name__=="__main__":
    main()
