"""BCT S6 genuine bounded 60-article public-source reentry, research-only.

Reuses immutable S6 316-item plan and original canonical SQLite. Tests latest
sidecar generation for each selected ID; fetches only IDs still absent via
the existing safe public original acquisition/screening engine. Never publishes
the temporary candidate JSON or original body/cache to GitHub/Actions.

A FULL body or a DEMAND/SUPPLY tag is not an independently qualified shortage.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from bct.objective_lock import require_objective,stamp_export
from bct.future_body import read_cached_body
from bct.future_bottleneck import run as screened_originals, VERSION as CANDIDATE_VERSION
from bct_s6_316_sourcefree_intake import (
    fresh_readback as verify_previous_research,
    read_canonical, PINNED_CANONICAL_SHA,PINNED_DATA,
    sha,canon
)
from bct_s6_canonical_article_id_join import fetch_canonical_sqlite
from bct_s6_full_sidecar_reconcile import (
    get_manifest,restore_exact,branch_head,SIDE_BRANCH
)

FORMAT="bct-s6-60-real-original-reentry-v1"
HOLD="NOT_EVALUATED_INDEPENDENT_ELIGIBLE_SOURCE_PAIR"
PLANNED=60
COHORT=316
HEAD_RE="^[0-9a-f]{40}$"
SHA_RE=re.compile("^[0-9a-f]{64}$")
KNOWN_BODIES={"FULL","PARTIAL","UNAVAILABLE"}
KNOWN_ROLES={"DEMAND","SUPPLY","RELIEF","CHANGE"}
PRIVATE_RAW={"body","html","raw","url","title","article_text","source_quote",
             "original_bytes","public_article_body","private_body"}
def guard(ok,why):
    if not ok:raise ValueError("BCT_S6_60_"+why)
def jfile(path):
    return json.loads(Path(path).read_text())

def checked_plan(previous_dir,canon_rows):
    check=verify_previous_research(previous_dir)
    guard(check.get("status")=="PASS_S6_316_SOURCE_FREE_RESEARCH_DB_FRESH_REQUERY"
          and check.get("articles")==COHORT and check.get("planned_only")==PLANNED
          and check.get("hold_targets")==22 and check.get("source_bound_facts")==20,
          "316_PREDECESSOR_PROOF_NOT_VERIFIED")
    summary=jfile(Path(previous_dir)/"s6-research-summary.json")
    require_objective(summary)
    guard(summary.get("format")=="bct-s6-316-rss-source-bound-intake-v1"
          and summary.get("canonical_commit_sha")==PINNED_DATA
          and summary.get("canonical_sqlite_sha256")==PINNED_CANONICAL_SHA
          and summary.get("source_reentry_plan_status")=="PLAN_ONLY_NOT_EXECUTED"
          and summary.get("operating_research_DB_merge")==
              "NOT_RUN_RESEARCH_ISOLATED_SQLITE_ONLY"
          and summary.get("research_fact_promotable_strict_pairs")==0,
          "PREDECESSOR_SEALED_INTAKE_CHANGED")
    rows={sha(r["id"]):r for r in canon_rows}
    guard(len(rows)==len(canon_rows)==10992,"CANONICAL_RSS_IDS_NOT_EXACT")
    with sqlite3.connect((Path(previous_dir)/"s6-research-sourcefree.sqlite3").resolve().as_uri()+"?mode=ro",uri=True) as db:
        plan=db.execute("SELECT id_sha,ordinal FROM source_reentry_plan ORDER BY ordinal").fetchall()
        intake=db.execute("SELECT id_sha,sha,payload FROM article_intake").fetchall()
    guard(len(plan)==PLANNED and [x[1] for x in plan]==list(range(1,PLANNED+1)),
          "ORIGINAL_PLAN_ORDER_CHANGED")
    previously={}
    for idsha,payload_sha,payload in intake:
        guard(sha(payload)==payload_sha and idsha not in previously,
              "PRIOR_316_HASHED_CASE_TAMPERED")
        c=json.loads(payload)
        guard(c.get("id_sha256")==idsha and
              c.get("work_state")=="SOURCE_RECHECK_ELIGIBLE_UNKNOWN_PRIOR_BODY" and
              c.get("qualifying_source_evidence_count")==0,
              "PRIOR_RSS_ONLY_DISPOSITION_FALSIFIED")
        previously[idsha]=c
    guard(len(previously)==COHORT and set(previously).issubset(rows),
          "PINNED_316_NOT_CANONICAL_SUBSET")
    selected=[]
    for key,n in plan:
        guard(key in previously and key in rows,"PLANNED_ARTICLE_NOT_IN_PRIOR_316")
        row=rows[key]
        expected=sha((row["url"]+row["updated_at"]).encode("utf-8"))
        guard(previously[key]["source_fingerprint_sha256"]==expected,
              "SOURCE_METADATA_VERSION_DIFFERS_FROM_PRIOR")
        selected.append({"id_sha256":key,"source":row})
    guard(len({r["source"]["id"] for r in selected})==PLANNED,
          "PLANNED_SOURCE_ID_NOT_UNIQUE")
    return selected,summary

def gate_latest_sidecar(results,selected):
    guard(type(results)==dict and len(results)>=10676,
          "CURRENT_RESULTS_MISSING_OR_OLDER_GENERATION")
    skipped=[];due=[]
    for case in selected:
        id=case["source"]["id"]
        if id in results:
            skipped.append(case)
        else:
            due.append(case)
    guard(len(due)+len(skipped)==PLANNED and
          not {x["id_sha256"] for x in due}&{x["id_sha256"] for x in skipped},
          "PLAN_COHORT_NOT_DISJOINT")
    return due,skipped

def strict_source_receipt(record):
    """Never infer verified provenance from FULL, metadata or RSS timestamp."""
    body_sha=record.get("current_body_sha256") or record.get("body_sha256")
    evidence=record.get("provenance_evidence")
    okay=(record.get("body_status")=="FULL"
          and record.get("provenance_verified") is True
          and record.get("publication_verified") is True
          and isinstance(body_sha,str) and SHA_RE.fullmatch(body_sha)
          and isinstance(evidence,dict)
          and evidence.get("body_sha256")==body_sha
          and isinstance(evidence.get("raw_sha256"),str)
          and SHA_RE.fullmatch(evidence["raw_sha256"])
          and isinstance(record.get("origin_id"),str)
          and record["origin_id"] not in ("","UNKNOWN")
          and isinstance(record.get("origin_publisher"),str)
          and record["origin_publisher"] not in ("","UNKNOWN"))
    return bool(okay)

def sourcefree_projection(selected,old,processed,cache_dir,sidecar_sha,manifest_sha):
    guard(re.fullmatch(HEAD_RE,sidecar_sha) is not None
          and isinstance(manifest_sha,str) and SHA_RE.fullmatch(manifest_sha),
          "UNPINNED_SOURCE_GENERATION")
    due,skipped=gate_latest_sidecar(old,selected)
    dueids={c["source"]["id"] for c in due}
    guard(type(processed)==dict and set(processed)==dueids,
          "EXECUTED_ARTICLES_DO_NOT_MATCH_DUE_COHORT")
    table=[];facts=[]
    for index,c in enumerate(selected,1):
        row=c["source"];id=row["id"];key=c["id_sha256"]
        if id not in dueids:
            table.append({
                "plan_ordinal":index,"id_sha256":key,
                "attempt_status":"SKIPPED_ALREADY_PRESENT_IN_NEWER_SIDECAR",
                "source_body_status":"PREVIOUS_RESULT_NOT_REPROCESSED",
                "verified_public_original":False,
                "publication_verified":False,
                "new_source_bound_research_fact_hints":0,
                "hash_version":"NOT_REPROCESSED",
                "source_error_codes":[],
                "auto_retries_added_to_operating_DB":0,
                "auto_promotions":0,
                "source_date_or_original_text_exported":False})
            continue
        result=processed[id]
        body_status=result.get("body_status")
        guard(body_status in KNOWN_BODIES,"ACTUAL_SOURCE_BODY_STATUS_INVALID")
        fingerprint=sha((row["url"]+row["updated_at"]).encode())
        guard(result.get("fingerprint")==fingerprint and
              result.get("id")==id,"ACTUAL_SOURCE_INPUT_REBOUND")
        acq=(result.get("acquisition") or {}).get("versions",{}).get(fingerprint,{})
        history=acq.get("history")
        guard(isinstance(history,list) and len(history)==1
              and history[0].get("trigger")=="SCHEDULED",
              "ACTUAL_SOURCE_ATTEMPT_RECEIPT_MISSING")
        access=result.get("access_diagnostic") or {}
        errors=[]
        for reason in (result.get("reasons") or []):
            if isinstance(reason,str) and re.fullmatch("[A-Z][A-Z0-9_]{1,63}",reason):
                errors.append(reason)
        if isinstance(access,dict) and isinstance(access.get("category"),str):
            category=access["category"]
            if re.fullmatch("[A-Z][A-Z0-9_]{1,63}",category):
                errors.append(category)
        errors=sorted(set(errors))[:15]
        version=result.get("current_body_sha256") or result.get("body_sha256")
        if version is not None:
            guard(isinstance(version,str) and SHA_RE.fullmatch(version),
                  "ACTUAL_SOURCE_VERSION_HASH_INVALID")
        verified=strict_source_receipt(result)
        if body_status!="FULL":
            guard(not verified,"UNAVAILABLE_BODY_MUST_NEVER_BE_A_PRIMARY_PROOF")
        body=read_cached_body(cache_dir,version) if version else None
        if body is not None:
            guard(sha(body)==version and len(body)>0,
                  "CACHED_SOURCE_TEXT_NOT_BOUND_TO_VERSION")
        if body_status in ("FULL","PARTIAL"):
            guard(body is not None,"EXTRACTED_SOURCE_BODY_CACHE_MISSING")
        for f in result.get("scope_facts",[]):
            if not verified:
                break
            loc=f.get("locator")
            if not isinstance(loc,dict):
                continue
            start,end=loc.get("start"),loc.get("end")
            if (type(start) is not int or type(end) is not int or
                not 0<=start<end<=len(body or "") or
                f.get("role") not in KNOWN_ROLES):
                continue
            original=body[start:end]
            facts.append({
               "fact_sha256":sha(canon([key,version,start,end,f.get("role"),sha(original)])),
               "id_sha256":key,
               "body_sha256":version,
               "span_sha256":sha(original),
               "start":start,"end":end,
               "role":f["role"],
               "target_name_sha256":sha(str(f.get("target") or "UNKNOWN").casefold()),
               "classification":"SOURCE_BOUND_RESEARCH_HINT_NOT_INDEPENDENT_ELIGIBLE_PAIR",
               "strict_economic_pair_admitted":False
            })
        table.append({
            "plan_ordinal":index,"id_sha256":key,
            "attempt_status":"PUBLIC_SOURCE_ACQUISITION_ATTEMPTED",
            "source_body_status":body_status,
            "verified_public_original":verified,
            "publication_verified":result.get("publication_verified") is True,
            "new_source_bound_research_fact_hints":
                sum(f["id_sha256"]==key for f in facts),
            "hash_version":version or "UNKNOWN",
            "source_error_codes":errors,
            "auto_retries_added_to_operating_DB":0,
            "auto_promotions":0,
            "source_date_or_original_text_exported":False
        })
    guard(len(table)==PLANNED and len({r["id_sha256"] for r in table})==PLANNED
          and len({f["fact_sha256"] for f in facts})==len(facts)
          and all(r["auto_promotions"]==0 for r in table),
          "ACTUAL_REENTRY_COUNTS_OR_FACT_KEYS_INVALID")
    return table,facts,len(due),len(skipped)

def summarize(records,facts,attempted,skipped,sidecar_sha,manifest_sha,source_receipt):
    counts=dict(sorted(Counter(r["source_body_status"] for r in records
                     if r["attempt_status"]=="PUBLIC_SOURCE_ACQUISITION_ATTEMPTED").items()))
    failures=dict(sorted(Counter(code for r in records for code in r["source_error_codes"]).items()))
    verified=sum(r["verified_public_original"] for r in records)
    guard(len(records)==PLANNED
          and attempted+skipped==PLANNED
          and sum(counts.values())==attempted
          and len(facts)==sum(r["new_source_bound_research_fact_hints"] for r in records)
          and all(r["source_body_status"]=="FULL" for r in records if r["verified_public_original"]),
          "REENTRY_OUTPUT_INTERNAL_CONSISTENCY")
    return stamp_export({
        "format":FORMAT,
        "status":"PASS_ACTUAL_PUBLIC_REENTRY_ATTEMPTS_AND_RESEARCH_HOLD",
        "scope":"EXACT_S6_SELECTED_60_PINNED_RSS_SOURCE_URLS_READONLY_BACKFILL",
        "sample_historical_RSS_snapshot_sha256":PINNED_CANONICAL_SHA,
        "historical_data_commit":PINNED_DATA,
        "sidecar_generation_checked":sidecar_sha,
        "sidecar_document_sha256":manifest_sha,
        "input_S6_research_sqlite_sha256":source_receipt["sqlite_sha256"],
        "planned_selected":PLANNED,
        "actual_eligible_source_attempts":attempted,
        "skipped_existing_current_sidecar_record":skipped,
        "actual_acquired_body_states":counts,
        "source_issue_counts":failures,
        "new_strict_original_verified":verified,
        "new_source_bound_research_fact_hints":len(facts),
        "source_fact_hints_are_not_independent_qualified_pairs":True,
        "retained_target_hold_count":22,
        "prior_research_fact_codes_preserved":20,
        "research_pair_admitted":0,
        "forecast_candidate_or_LIVE_promotions":0,
        "original_source_bodies_or_urls_persisted":False,
        "model_API_or_private_CPU_calls":0,
        "existing_operating_CAS_mutations":0,
        "operating_research_DB_merge":"NOT_RUN_ONLY_ISOLATED_RESEARCH_RUN",
        "new_source_text_retained_outside_actions":"NO",
        "historical_511_sector_rank_updated":False,
        "remaining_S6_gate":"VALIDATE_ONLY_INDEPENDENT_SAME_TARGET_SUPPLY_DEMAND_THEN_OPERATING_RESEARCH_CAS",
        "forecast_accuracy":"UNVERIFIED"
    })

def persist(path,summary,records,facts):
    path=Path(path)
    guard(not path.exists(),"OUTPUT_ALREADY_EXISTS")
    path.mkdir(parents=True)
    f=path/"s6-60-sourcefree.sqlite3"
    with sqlite3.connect(f) as con:
        con.execute("CREATE TABLE source_attempts(id_sha TEXT PRIMARY KEY,sha TEXT NOT NULL,payload TEXT NOT NULL)")
        con.execute("CREATE TABLE source_bound_hints(fact_sha TEXT PRIMARY KEY,id_sha TEXT NOT NULL,payload_sha TEXT NOT NULL,payload TEXT NOT NULL)")
        for row in records:
            txt=canon(row)
            con.execute("INSERT INTO source_attempts VALUES(?,?,?)",
                       (row["id_sha256"],sha(txt),txt))
        for row in facts:
            txt=canon(row)
            con.execute("INSERT INTO source_bound_hints VALUES(?,?,?,?)",
                       (row["fact_sha256"],row["id_sha256"],sha(txt),txt))
    result=dict(summary)
    result["research_sqlite_sha256"]=sha(f.read_bytes())
    (path/"s6-60-execution.json").write_text(canon(result)+"\n")
    fresh_readback(path)
    return result

def fresh_readback(path):
    p=Path(path)
    report=jfile(p/"s6-60-execution.json")
    require_objective(report)
    f=p/"s6-60-sourcefree.sqlite3"
    guard(sha(f.read_bytes())==report.get("research_sqlite_sha256"),
          "SOURCEFREE_SQLITE_CHANGED")
    with sqlite3.connect(f.resolve().as_uri()+"?mode=ro",uri=True) as db:
        guard(db.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "SOURCEFREE_SQLITE_INTEGRITY")
        states=Counter()
        rows=db.execute("SELECT id_sha,sha,payload FROM source_attempts").fetchall()
        for key,hashval,payload in rows:
            guard(sha(payload)==hashval,"SOURCE_RECEIPT_HASH_CHANGED")
            rec=json.loads(payload)
            guard(rec["id_sha256"]==key and not PRIVATE_RAW.intersection(rec),
                  "RAW_SOURCE_CONTENT_OR_ARTICLE_ID_LEAK")
            if rec["attempt_status"]=="PUBLIC_SOURCE_ACQUISITION_ATTEMPTED":
                states[rec["source_body_status"]]+=1
            guard(rec["auto_promotions"]==rec["auto_retries_added_to_operating_DB"]==0,
                  "UNAUTHORIZED_OPERATING_WRITE")
        hints=db.execute("SELECT fact_sha,id_sha,payload_sha,payload FROM source_bound_hints").fetchall()
        for fact_sha,id_sha,payload_sha,payload in hints:
            guard(sha(payload)==payload_sha,"FACT_PROOF_PAYLOAD_CHANGED")
            rec=json.loads(payload)
            guard(rec["fact_sha256"]==fact_sha
                  and rec["id_sha256"]==id_sha
                  and rec["strict_economic_pair_admitted"] is False
                  and rec["classification"]=="SOURCE_BOUND_RESEARCH_HINT_NOT_INDEPENDENT_ELIGIBLE_PAIR"
                  and not PRIVATE_RAW.intersection(rec),"FALSE_FACT_EVIDENCE_PROMOTION")
    guard(len(rows)==PLANNED and
          len(hints)==report["new_source_bound_research_fact_hints"]
          and dict(sorted(states.items()))==report["actual_acquired_body_states"]
          and report["actual_eligible_source_attempts"]+report["skipped_existing_current_sidecar_record"]==PLANNED
          and report["forecast_candidate_or_LIVE_promotions"]==
              report["research_pair_admitted"]==report["existing_operating_CAS_mutations"]==0
          and report["operating_research_DB_merge"]==
              "NOT_RUN_ONLY_ISOLATED_RESEARCH_RUN",
          "FRESH_SQLITE_SUMMARY_OR_INDEPENDENCE_CHANGED")
    return {"status":"PASS_S6_60_REAL_ATTEMPT_SOURCE_FREE_FRESH_READBACK",
            "planned":len(rows),"attempted":report["actual_eligible_source_attempts"],
            "skipped":report["skipped_existing_current_sidecar_record"],
            "body_states":dict(sorted(states.items())),
            "strict_source_verified":report["new_strict_original_verified"],
            "source_bound_hints":len(hints),
            "eligible_independent_pairs":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--previous",type=Path)
    p.add_argument("--sidecar-head",type=str)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        print("BCT_S6_60_REQUERY="+canon(fresh_readback(args.out)),flush=True)
        return
    guard(args.previous is not None and
          isinstance(args.sidecar_head,str) and re.fullmatch(HEAD_RE,args.sidecar_head),
          "IMMUTABLE_SOURCE_INPUTS_REQUIRED")
    guard(branch_head(SIDE_BRANCH)==args.sidecar_head,
          "SIDE_BRANCH_MOVED_BEFORE_ORIGINALS")
    prior=jfile(args.previous/"s6-research-summary.json")
    require_objective(prior)
    raw=fetch_canonical_sqlite()
    with tempfile.TemporaryDirectory(prefix="bct-s6-60-private-source-") as temp:
        directory=Path(temp)
        meta,review,aux=read_canonical(raw,directory/"original-canonical.sqlite3")
        selection,parent=checked_plan(args.previous,meta)
        m,_=get_manifest("future-candidates.json",args.sidecar_head)
        candidate,readback=restore_exact(m,workers=5)
        guard(readback.get("fetched_shards")==len(m["shards"]) and
              isinstance(candidate.get("results"),dict),
              "LATEST_SIDECAR_IMMUTABLE_RESTORE_FAILED")
        due,skipped=gate_latest_sidecar(candidate["results"],selection)
        results={}
        private_cache=directory/"original-private-cache"
        if due:
            private_output=directory/"screened-local-only.json"
            private_output.write_text(json.dumps(
                {"version":CANDIDATE_VERSION,"results":{}})+"\n")
            generated=screened_originals(
                 directory/"original-canonical.sqlite3",
                 private_output,limit=len(due),workers=6,cache_dir=private_cache,
                 trigger="SCHEDULED",
                 trigger_id="s6-60-immutable-source-20261116",
                 detection_mode="BACKFILL",
                 document_ids=[x["source"]["id"] for x in due],
            )
            results=generated.get("results",{})
        records,facts,n_due,n_skip=sourcefree_projection(
            selection,candidate["results"],results,private_cache,
            args.sidecar_head,m["document_sha256"])
        report=summarize(records,facts,n_due,n_skip,args.sidecar_head,
                         m["document_sha256"],prior)
        # Existing operating source ref is never used for a mutation. A moved
        # ref invalidates any claim that this cohort is still the newest state.
        current=branch_head(SIDE_BRANCH)
        if current!=args.sidecar_head:
            report["current_sidecar_snapshot_now"]="CHANGED_AFTER_SOURCE_READ"
            report["status"]="PASS_PINNED_SOURCE_READ_CURRENT_BRANCH_ADVANCED_RECHECK_REQUIRED"
            report["remaining_S6_gate"]="RECHECK_NEW_SIDECAR_BEFORE_ANY_CAS"
        result=persist(args.out,report,records,facts)
    print("BCT_S6_60_ACTUAL_REENTRY="+canon({
        "status":result["status"],"attempted":result["actual_eligible_source_attempts"],
        "skipped_already_recorded":result["skipped_existing_current_sidecar_record"],
        "body_states":result["actual_acquired_body_states"],
        "strict_verified_public_originals":result["new_strict_original_verified"],
        "research_only_source_bound_hints":result["new_source_bound_research_fact_hints"],
        "source_failure_reason_codes":result["source_issue_counts"],
        "new_strict_pairs":result["research_pair_admitted"],
        "operating_writes":result["existing_operating_CAS_mutations"]}),flush=True)

if __name__=="__main__":
    main()
