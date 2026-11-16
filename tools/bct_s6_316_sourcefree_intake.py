"""BCT S6: all 316 operating RSS-only IDs + source-bound public research facts.

Read-only, pinned canonical SQLite + immutable prior artifact IDs. This is a
research-only intake; it does not create verified independent physical pairs,
claim failed original acquisition without a source receipt, or change LIVE.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from bct.objective_lock import require_objective,stamp_export
from bct_session7_queue_monitor import classify,plan_work
from bct_s6_canonical_article_id_join import (
    fetch_canonical_sqlite, PINNED_CANONICAL_SHA, PINNED_DATA, PINNED_SIDE,
    PINNED_RSS, PINNED_RESULTS
)
from bct_s6_canonical_article_id_join import readback as verify_id_join
from bct_s5_22_target_disposition import fresh_readback as verify_s5_hold
from bct_s5_supplier_fact_followon import requery as verify_supplier
from bct_s5_quantitative_capacity_audit import fresh_readback as verify_standard

FORMAT="bct-s6-316-rss-source-bound-intake-v1"
SOURCE_FACTS_FORMAT="bct-s6-sourcebound-research-fact-v1"
SOURCE_TARGET="unobligated-haleu-us-qualified-supply"
ASOF=datetime.fromisoformat("2026-11-16T10:08:00+00:00")
EXPECTED_RSS=10992
EXPECTED_MATCHED=10676
EXPECTED_MISSING=316
EXPECTED_TARGET_HOLDS=22
EXPECTED_SOURCE_FACTS=20
EXPECTED_DISTINCT_SUPPLIER=8
EXPECTED_STANDARD=12
HASH64=re.compile("^[a-f0-9]{64}$")
SOURCE_GROUPS={
    "bwxt_antares_issuer":"ANTARES_BWXT_FUEL_FRAMEWORK",
    "centrus_issuer_q3":"CENTRUS_2026Q3_SINGLE_DISCLOSURE",
    "centrus_official_8k_pdf":"CENTRUS_2026Q3_SINGLE_DISCLOSURE",
    "standard_2026q3_sec_10q":"ANTARES_STANDARD_FABRICATION_AND_CAPACITY_2026Q3",
}
BAD_RAW={"body","html","original_text","source_quote","article_body","private_token"}
def canon(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def sha(x):
    return hashlib.sha256(x if isinstance(x,bytes) else x.encode("utf-8")).hexdigest()
def guard(ok,why):
    if not ok:raise ValueError("BCT_S6_316_"+why)
def json_file(p):
    return json.loads(Path(p).read_text())

def validate_parents(join_dir,s5_dir,standard_dir,supplier_dir):
    j=verify_id_join(join_dir)
    h=verify_s5_hold(s5_dir)
    d=verify_standard(standard_dir)
    s=verify_supplier(supplier_dir)
    old=json_file(Path(join_dir)/"s6-article-id-join.json")
    s5=json_file(Path(s5_dir)/"s5-closed-review.json")
    standard=json_file(Path(standard_dir)/"summary.json")
    supplier=json_file(Path(supplier_dir)/"summary.json")
    require_objective(old)
    require_objective(s5)
    require_objective(standard)
    require_objective(supplier)
    guard(j=={"status":"PASS_PINNED_RSS_AND_SIDECAR_FRESH_SQLITE_ID_JOIN",
              "articles":EXPECTED_RSS,"results":EXPECTED_MATCHED,
              "matched":EXPECTED_MATCHED,"missing_result":EXPECTED_MISSING,
              "sidecar_only":0},"EXACT_PREVIOUS_ID_JOIN_NOT_VERIFIED")
    guard(old.get("data_commit_sha")==PINNED_DATA and
          old.get("sidecar_commit_sha")==PINNED_SIDE and
          old.get("canonical_sqlite_sha256")==PINNED_CANONICAL_SHA and
          old.get("id_join_counts")=={"BOTH":EXPECTED_MATCHED,"CANONICAL_ONLY":EXPECTED_MISSING}
          and old.get("canonical_without_sidecar_statuses")=={"active":EXPECTED_MISSING},
          "MISMATCHED_COHORT_GENERATION")
    guard(h.get("cases")==22 and h.get("HOLD")==22 and
          s5.get("qualified")==0 and s5.get("rejected")==0 and
          s5.get("full_10k_article_research_audit")=="NOT_PERFORMED",
          "S5_TARGET_HOLD_STATUS_INVALID")
    guard(d.get("originals")==2 and d.get("fact_count")==12 and
          standard.get("firm_contract_cumulative_MTU_by_2030")==1 and
          standard.get("Antares_customer_optional_MTU_not_firm")==7 and
          standard.get("Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30")==0.5 and
          standard.get("confirmed_shortage")=="NOT_ESTABLISHED",
          "STANDARD_SOURCE_FACTS_NOT_VERIFIED")
    guard(s.get("cases")==4 and s.get("fact_count")==8 and
          supplier.get("strict_pair_evaluated") is False and
          supplier.get("LIVE_writes")==0 and
          supplier.get("verified_distinct_fact_count")==8 and
          supplier.get("public_source_bodies_captured")==3,
          "SUPPLIER_SOURCE_FACTS_NOT_VERIFIED")
    return {"join":old,"target":s5,"standard":standard,"supplier":supplier}

def read_canonical(raw,dbpath):
    guard(sha(raw)==PINNED_CANONICAL_SHA and raw.startswith(b"SQLite format 3\x00"),
          "CANONICAL_GENERATION_OR_BYTES")
    Path(dbpath).write_bytes(raw)
    with sqlite3.connect(Path(dbpath).resolve().as_uri()+"?mode=ro&immutable=1",uri=True) as db:
        guard(db.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "CANONICAL_DB_INTEGRITY")
        columns={r[1] for r in db.execute("PRAGMA table_info(radar_items)")}
        required={"id","source","url","title","snippet","published_at",
                  "collected_at","updated_at","status"}
        guard(required.issubset(columns),"MISSING_CANONICAL_RSS_METADATA")
        items=db.execute("SELECT id,source,url,title,snippet,published_at,"
                         "collected_at,updated_at,status "
                         "FROM radar_items ORDER BY id").fetchall()
        guard(len(items)==EXPECTED_RSS and
              len({r[0] for r in items})==EXPECTED_RSS and
              all(r[8]=="active" for r in items),
              "CANONICAL_COUNT_OR_ACTIVE_STATUS_CHANGED")
        optional=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name='rss_ai_reviews'").fetchone()
        review_by_id=defaultdict(Counter)
        separate_review_total=0
        if optional:
            cols={r[1] for r in db.execute("PRAGMA table_info(rss_ai_reviews)")}
            guard({"radar_item_id","status"}.issubset(cols),"RSS_AI_REVIEW_SCHEMA_CHANGED")
            for row_id,status in db.execute(
                "SELECT radar_item_id,status FROM rss_ai_reviews"):
                guard(status in ("OK","ERROR"),"SEPARATE_RSS_AI_STATUS_NOT_KNOWN")
                review_by_id[row_id][status]+=1
                separate_review_total+=1
    rows=[dict(zip(("id","source","url","title","snippet","published_at",
                    "collected_at","updated_at","status"),r)) for r in items]
    return rows,review_by_id,{
       "rss_ai_separate_table_present":bool(optional),
       "rss_ai_review_rows_full_corpus":separate_review_total,
    }

def read_previous_hashed_ids(join_dir):
    sql=Path(join_dir)/"s6-article-id-join.sqlite3"
    with sqlite3.connect(sql.resolve().as_uri()+"?mode=ro",uri=True) as db:
        records=db.execute("SELECT id_sha,kind,body_state,canonical_state "
                           "FROM article_join").fetchall()
    guard(len(records)==EXPECTED_RSS and
          len({r[0] for r in records})==EXPECTED_RSS,
          "PREVIOUS_HASHED_ID_JOIN_NOT_EXHAUSTIVE")
    classes=Counter(r[1] for r in records)
    guard(classes=={"BOTH":EXPECTED_MATCHED,"CANONICAL_ONLY":EXPECTED_MISSING},
          "PREVIOUS_COHORT_WRONG")
    return {r[0]:(r[1],r[2],r[3]) for r in records}

def classify_316(rows,review_by_id,prior_id_map,canonical_sha):
    guard(len(rows)==EXPECTED_RSS and canonical_sha==PINNED_CANONICAL_SHA,
          "CANONICAL_INPUT_NOT_PINNED")
    hashed={sha(row["id"]):row for row in rows}
    guard(len(hashed)==EXPECTED_RSS and set(hashed)==set(prior_id_map),
          "CANONICAL_AND_PREVIOUS_HASHED_IDS_MISMATCH")
    intake=[];queue_rows=[];review_statuses=Counter()
    for hashed_id in sorted(hashed):
        oldkind,oldbody,oldstatus=prior_id_map[hashed_id]
        row=hashed[hashed_id]
        guard(oldstatus==row["status"]=="active",
              "CANONICAL_STATUS_DRIFT")
        if oldkind=="BOTH":
            guard(isinstance(oldbody,str) and oldbody,
                  "PRIOR_MATCHED_BODY_STATE_MISSING")
            continue
        guard(oldkind=="CANONICAL_ONLY" and oldbody is None,
              "UNEXPECTED_MISSING_SIDECAR_EVIDENCE")
        decision=classify(row,None,ASOF)
        guard(decision["sidecar_record_present"] is False and
              decision["body_status"]=="NOT_IN_SIDECAR" and
              not decision["original_provenance_verified"],
              "FALSE_ORIGINAL_STATUS_ON_RSS_ONLY_ARTICLE")
        reviews=review_by_id.get(row["id"],Counter())
        review_statuses.update(reviews)
        # RSS AI is title/snippet annotation, not original body or CPU reading.
        separate=("RSS_TITLE_AI_OK_SEPARATE_NOT_CPU" if reviews["OK"] else
                  "RSS_TITLE_AI_ERROR_SEPARATE_NOT_CPU" if reviews["ERROR"] else
                  "NO_RSS_AI_ANNOTATION_RECORDED")
        action=decision["work_action"]
        valid=action=="FETCH_OR_RECHECK_ORIGINAL"
        state="SOURCE_RECHECK_ELIGIBLE_UNKNOWN_PRIOR_BODY" if valid else "SOURCE_METADATA_INVALID_HOLD"
        guard(action in ("FETCH_OR_RECHECK_ORIGINAL","HOLD_INVALID_SOURCE_URL"),
              "MISSING_SIDECAR_CANNOT_HAVE_PROVEN_FAILURE_OR_COMPLETION")
        entry={
          "id_sha256":hashed_id,
          "work_state":state,
          "screening_priority":decision["metadata_priority"],
          "review_lane":decision["review_lane"],
          "recency_as_of_pin":decision["recency_bucket"],
          "source_fingerprint_sha256":decision["source_fingerprint"],
          "source_metadata_host_sha256":sha((row["source"] or "").casefold()),
          "original_body_status":"NOT_IN_OPERATING_SIDECAR_UNKNOWN_PHYSICAL_STATE",
          "source_access_failure_verified":False,
          "source_retry_and_attempts":"NOT_RECORDED_IN_OPERATING_SIDECAR",
          "independent_CPU_read_status":"NOT_EVALUATED_FROM_RSS_METADATA",
          "separate_rss_title_ai":separate,
          "separate_rss_ai_ok_count":reviews["OK"],
          "separate_rss_ai_error_count":reviews["ERROR"],
          "narrow_screening_hint_count":len(decision["narrow_signal_codes"].split("|"))
             if decision["narrow_signal_codes"] else 0,
          "qualifying_source_evidence_count":0,
          "record_confidence":"ID_JOIN_VERIFIED_NO_ORIGINAL_ACQUISITION_PROOF",
          "original_source_url_or_title_exported":False
        }
        intake.append(entry)
        if valid:
            queue_rows.append({**decision,"hashed_article_id":hashed_id})
    guard(len(intake)==EXPECTED_MISSING and
          len({x["id_sha256"] for x in intake})==EXPECTED_MISSING and
          all(x["qualifying_source_evidence_count"]==0 for x in intake),
          "INCOMPLETE_316_INTAKE_OR_FALSE_PAIR")
    # Fair selection is a PLAN only, never proof a job was executed.
    planned=plan_work(queue_rows,budget=120,fresh_fraction=0.4,max_host=6)
    selected=[sha(x["article_id"]) for x in planned]
    guard(len(selected)==len(set(selected)) and
          set(selected).issubset({x["id_sha256"] for x in intake}),
          "REENTRY_SELECTION_NOT_SOURCE_BOUND")
    return intake,selected,dict(sorted(review_statuses.items()))

def query_cases(dbpath,table,keyfield,payloadfield):
    with sqlite3.connect(Path(dbpath).resolve().as_uri()+"?mode=ro",uri=True) as db:
        guard(db.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "SOURCE_FREE_INPUT_SQLITE_CORRUPT")
        rows=db.execute(f"SELECT {keyfield},{payloadfield} FROM {table} ORDER BY {keyfield}").fetchall()
    return [(i,json.loads(payload)) for i,payload in rows]

def combine_target_holds(s5_dir):
    records=query_cases(Path(s5_dir)/"s5-to-s6-research.sqlite3",
                        "cases","id","payload")
    guard(len(records)==EXPECTED_TARGET_HOLDS,"S5_22_TARGETS_NOT_PRESENT")
    out=[]
    for key,case in records:
        guard(key==case.get("case_id") and
              case.get("research_disposition")=="HOLD" and
              case.get("source_independent_pair_verified") is False and
              case.get("known_annual_deficit_measured")=="UNKNOWN",
              "HOLD_TARGET_FALSIFIED_OR_PROMOTED")
        out.append({
            "target_id":case["target_id"],"source_case_sha256":key,
            "disposition":"HOLD", "historical_review_count":case["historical_registration_review_count"],
            "previous_display_stage":case["prior_display_stage_2026_09_30"],
            "qualifying_independent_pairs":"NOT_EVALUATED_UNDER_S5_PROVENANCE",
            "candidate_promotion":False,
        })
    guard(len({x["target_id"] for x in out})==22,
          "DUPLICATE_REGISTERED_TARGET")
    return sorted(out,key=lambda x:x["target_id"])

def _source_receipt(c,loc):
    raw=c.get("raw_sha256")
    visible=c.get("visible_sha256")
    guard(isinstance(raw,str) and HASH64.fullmatch(raw) and
          isinstance(visible,str) and HASH64.fullmatch(visible),
          "SOURCE_BYTES_NO_SHA")
    guard(type(loc)==dict and
          type(loc.get("start")) is int and type(loc.get("end")) is int and
          loc["start"]<loc["end"] and loc["start"]>=0 and
          HASH64.fullmatch(str(loc.get("span_sha256",loc.get("source_span_sha256","")))),
          "FACT_SPAN_NOT_SOURCE_HASH_BOUND")
    return {"source_id":c["source_id"],
            "issuer":c.get("issuer","Standard Nuclear, Inc."),
            "raw_sha256":raw,"visible_sha256":visible,
            "span_sha256":loc.get("span_sha256",loc.get("source_span_sha256")),
            "start":loc["start"],"end":loc["end"],
            "source_attestation_level":"VISIBLE_ORIGINAL_RESEARCH_ONLY_NOT_STRICT_ELIGIBLE"}

def combined_research_facts(standard_dir,supplier_dir,target_ids):
    guard(SOURCE_TARGET in target_ids,"TARGET_REFERENCE_NOT_REGISTERED")
    st=query_cases(Path(standard_dir)/"research.sqlite3","cases","id","payload")
    su=query_cases(Path(supplier_dir)/"source-free.sqlite3","cases","id","record")
    guard(len(st)==2 and len(su)==4,
          "S5_SOURCE_PROOF_CASE_COUNTS_CHANGED")
    facts=defaultdict(list)
    meanings={}
    for sid,c in st:
        guard(sid==c.get("source_id"),"STANDARD_SOURCE_ID_REBOUND")
        if sid!="standard_2026q3_sec_10q":
            guard(c.get("status")=="ACCESS_HOLD","STANDARD_OTHER_PROOF_SHOULD_HOLD")
            continue
        guard(c.get("status")=="FETCHED_PUBLIC_ORIGINAL_RESEARCH_ONLY",
              "STANDARD_BODY_NOT_VERIFIED")
        f=c.get("fact_receipts",[])
        guard(len(f)==EXPECTED_STANDARD,"STANDARD_EXACT_FACT_COUNT_CHANGED")
        for r in f:
            guard(r.get("state")=="SOURCE_LOCATOR_HASH_VERIFIED" and
                  r.get("fact_id") and r.get("locator") and
                  type(r.get("value")) in (bool,int,float,str) and
                  r.get("meaning"),"STANDARD_EXTRACTED_FACT_NOT_SOURCE_BOUND")
            key=(SOURCE_GROUPS[sid],r["fact_id"])
            facts[key].append(_source_receipt(c,r["locator"]))
            meanings[key]=(r["meaning"],r["value"],r.get("unit","QUALITATIVE"))
    for sid,c in su:
        guard(sid==c.get("source_id") and
              c.get("qualified_customer_unreserved_supply_MTU")=="UNKNOWN" and
              c.get("LIVE_writes")==0,
              "SUPPLIER_RESEARCH_HOLD_CHANGED")
        if sid=="centrus_sec_q3_ex99":
            guard(c.get("status")=="ACCESS_HOLD","SEC_ACCESS_HOLD_NOT_PRESERVED")
            continue
        guard(sid in SOURCE_GROUPS and
              c.get("status")=="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY",
              "SUPPLIER_ISSUER_PROOF_NOT_ATTESTED")
        for r in c.get("facts",[]):
            guard(r.get("state")=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED"
                  and r.get("location") and r.get("fact_id")
                  and r.get("interpretation") and
                  type(r.get("value")) in (bool,int,float,str),
                  "SUPPLIER_FACT_NOT_ATTESTED")
            key=(SOURCE_GROUPS[sid],r["fact_id"])
            facts[key].append(_source_receipt(c,r["location"]))
            value=(r["interpretation"],r["value"],"EXPLICIT_SOURCE_SCOPE_CODE")
            if key in meanings:
                guard(meanings[key]==value,
                      "DUPLICATE_ISSUER_FACT_CONTRADICTORY")
            meanings[key]=value
    guard(len(facts)==EXPECTED_SOURCE_FACTS and
          sum(k[0]=="CENTRUS_2026Q3_SINGLE_DISCLOSURE" for k in facts)==5 and
          sum(k[0]=="ANTARES_BWXT_FUEL_FRAMEWORK" for k in facts)==3 and
          sum(k[0]=="ANTARES_STANDARD_FABRICATION_AND_CAPACITY_2026Q3" for k in facts)==12,
          "SOURCE_FACT_NUMBER_OR_CAUSAL_DEDUP_CHANGED")
    cases=[]
    for key in sorted(facts):
        causal,fid=key
        receipts=sorted(facts[key],key=lambda r:r["source_id"])
        guard(len({r["source_id"] for r in receipts})==len(receipts),
              "DUPLICATE_IDENTICAL_PUBLIC_ISSUER_RECEIPT")
        guard(len(receipts)==(2 if causal=="CENTRUS_2026Q3_SINGLE_DISCLOSURE" else 1),
              "SAME_DISCLOSURE_NOT_DEDUPED")
        interp,value,unit=meanings[key]
        cases.append({
          "fact_key_sha256":sha(canon([SOURCE_TARGET,causal,fid])),
          "target_id":SOURCE_TARGET,
          "causal_event":causal,"fact_id":fid,
          "source_bound_state":"RESEARCH_ONLY_SOURCE_SPAN_ATTESTED",
          "source_scope_interpretation":interp,
          "value":value,"unit":unit,
          "public_original_receipts":receipts,
          "strict_original_pair_eligible":False,
          "annual_same_scope_unreserved_supply":"UNKNOWN",
          "forecast_qualification":"NOT_EVALUATED_NO_SAME_PERIOD_ELIGIBLE_PAIR"
        })
    return cases

def build_summary(articles,queue,reviews,targets,facts,parents,aux):
    q=Counter(x["work_state"] for x in articles)
    priority=Counter(x["screening_priority"] for x in articles)
    separate=Counter(x["separate_rss_title_ai"] for x in articles)
    guard(len(targets)==22 and len(facts)==20 and len(articles)==316
          and len(queue)<=120 and len(set(queue))==len(queue),
          "CASE_COUNTS_NOT_VERIFIED")
    return stamp_export({
        "format":FORMAT,
        "status":"PASS_S6_316_ACTUAL_HASH_JOIN_CLASSIFICATION_AND_22_HOLD_20_SOURCE_FACT_INTAKE",
        "cohort_snapshot":"PINNED_2026_11_16_SOURCE_GENERATION_NOT_LIVE_REFRESH",
        "canonical_commit_sha":PINNED_DATA,
        "future_sidecar_commit_sha":PINNED_SIDE,
        "canonical_sqlite_sha256":PINNED_CANONICAL_SHA,
        "original_full_39_candidate_shards_reread":False,
        "prior_verified_full_shards_reused":True,
        "canonical_rss_articles":EXPECTED_RSS,
        "matched_prior_sidecar_results":EXPECTED_MATCHED,
        "articles_without_prior_sidecar":len(articles),
        "article_intake_actions":dict(sorted(q.items())),
        "article_metadata_priority":dict(sorted(priority.items())),
        "separate_rss_title_AI_annotations_in_missing_cohort":dict(sorted(reviews.items())),
        "separate_rss_title_AI_presence_by_article":dict(sorted(separate.items())),
        "ai_review_table_in_canonical":aux["rss_ai_separate_table_present"],
        "rss_ai_review_rows_entire_corpus":aux["rss_ai_review_rows_full_corpus"],
        "source_reentry_plan_max_120":len(queue),
        "source_reentry_plan_status":"PLAN_ONLY_NOT_EXECUTED",
        "actual_article_source_fails_proven":0,
        "actual_article_CPU_failed_proven":0,
        "article_original_body_verified_from_missing_sidecar":0,
        "research_hold_registered_target_records":len(targets),
        "research_source_bound_original_fact_records":len(facts),
        "research_fact_event_groups":dict(sorted(Counter(x["causal_event"] for x in facts).items())),
        "research_fact_promotable_strict_pairs":0,
        "independent_eligible_supply_demand_pair_evaluation":"NOT_RUN_MISSING_EXACT_PHYSICAL_SCOPE",
        "historical_511_published_record_count":"NOT_RECLASSIFIED",
        "operating_research_DB_merge":"NOT_RUN_RESEARCH_ISOLATED_SQLITE_ONLY",
        "S6_scoped_research_sqlite_intake":"READY_AFTER_FRESH_READBACK",
        "production_data_branch_writes":0,
        "production_sidecar_branch_writes":0,
        "LIVE_writes":0,"dashboard_writes":0,"model_inference_calls":0,
        "source_article_body_or_url_exported":False,
        "prior_source_receipts_sha256":{
            "join":parents["join"]["sqlite_sha256"],
            "target":parents["target"]["sqlite_sha256"],
            "standard":parents["standard"]["sqlite_sha256"],
            "supplier":parents["supplier"]["sql_sha256"]
        },
        "next_gate":"S6_EXECUTE_BOUNDED_REENTRY_THEN_VERIFY_REAL_SOURCE_RECEIPTS_AND_OPERATING_RESEARCH_CAS",
        "forecast_accuracy":"UNVERIFIED"
    })

def write_db(out,report,articles,queue,targets,facts):
    p=Path(out)
    guard(not p.exists(),"OUTPUT_EXISTS")
    p.mkdir(parents=True)
    file=p/"s6-research-sourcefree.sqlite3"
    with sqlite3.connect(file) as db:
        db.execute("CREATE TABLE article_intake(id_sha TEXT PRIMARY KEY,sha TEXT NOT NULL,payload TEXT NOT NULL)")
        db.execute("CREATE TABLE source_reentry_plan(id_sha TEXT PRIMARY KEY,ordinal INTEGER NOT NULL UNIQUE)")
        db.execute("CREATE TABLE target_holds(target_id TEXT PRIMARY KEY,sha TEXT NOT NULL,payload TEXT NOT NULL)")
        db.execute("CREATE TABLE research_facts(fact_sha TEXT PRIMARY KEY,target_id TEXT NOT NULL,sha TEXT NOT NULL,payload TEXT NOT NULL)")
        for x in articles:
            data=canon(x)
            db.execute("INSERT INTO article_intake VALUES(?,?,?)",(x["id_sha256"],sha(data),data))
        for n,key in enumerate(queue,1):
            db.execute("INSERT INTO source_reentry_plan VALUES(?,?)",(key,n))
        for x in targets:
            data=canon(x)
            db.execute("INSERT INTO target_holds VALUES(?,?,?)",(x["target_id"],sha(data),data))
        for x in facts:
            data=canon(x)
            db.execute("INSERT INTO research_facts VALUES(?,?,?,?)",
                       (x["fact_key_sha256"],x["target_id"],sha(data),data))
    result=dict(report)
    result["sqlite_sha256"]=sha(file.read_bytes())
    (p/"s6-research-summary.json").write_text(canon(result)+"\n")
    fresh_readback(p)
    return result

def fresh_readback(path):
    p=Path(path)
    r=json_file(p/"s6-research-summary.json")
    require_objective(r)
    f=p/"s6-research-sourcefree.sqlite3"
    guard(sha(f.read_bytes())==r.get("sqlite_sha256"),"SQLITE_BYTE_HASH_CHANGED")
    with sqlite3.connect(f.resolve().as_uri()+"?mode=ro",uri=True) as db:
        guard(db.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "INTEGRITY_CHECK_FAILED")
        n={}
        for table in ("article_intake","source_reentry_plan","target_holds","research_facts"):
            n[table]=db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
        for table,pk in (("article_intake","id_sha"),("target_holds","target_id"),
                         ("research_facts","fact_sha")):
            for key,h,text in db.execute("SELECT "+pk+",sha,payload FROM "+table):
                guard(sha(text)==h,"SOURCE_FREE_CASE_PAYLOAD_HASH_CHANGED")
                item=json.loads(text)
                guard(not (BAD_RAW & set(item)),
                      "ARTICLE_TEXT_OR_PRIVATE_DATA_LEAK")
                if table=="article_intake":
                    guard(item.get("id_sha256")==key and
                          item.get("qualifying_source_evidence_count")==0 and
                          item.get("original_source_url_or_title_exported") is False,
                          "FALSE_ARTICLE_SOURCE_PROVENANCE")
                if table=="target_holds":
                    guard(item.get("target_id")==key and
                          item.get("disposition")=="HOLD" and
                          item.get("candidate_promotion") is False,
                          "HOLD_TARGET_PROMOTED")
                if table=="research_facts":
                    guard(item.get("fact_key_sha256")==key and
                          item.get("strict_original_pair_eligible") is False and
                          item.get("forecast_qualification")==
                             "NOT_EVALUATED_NO_SAME_PERIOD_ELIGIBLE_PAIR" and
                          item.get("annual_same_scope_unreserved_supply")=="UNKNOWN",
                          "NONQUALIFIED_FACT_PROMOTED")
        states=dict(db.execute("SELECT json_extract(payload,'$.work_state'),COUNT(*) "
                               "FROM article_intake GROUP BY json_extract(payload,'$.work_state')"))
        plan_rows=list(db.execute("SELECT id_sha,ordinal FROM source_reentry_plan ORDER BY ordinal"))
        guard(len(plan_rows)==len(set(x[0] for x in plan_rows)) and
              [x[1] for x in plan_rows]==list(range(1,len(plan_rows)+1)),
              "REENTRY_PLAN_DUPLICATED")
        match=db.execute("SELECT COUNT(*) FROM source_reentry_plan p "
                         "LEFT JOIN article_intake a ON p.id_sha=a.id_sha "
                         "WHERE a.id_sha IS NULL").fetchone()[0]
    guard(n["article_intake"]==r["articles_without_prior_sidecar"]==EXPECTED_MISSING
          and n["target_holds"]==r["research_hold_registered_target_records"]==22
          and n["research_facts"]==r["research_source_bound_original_fact_records"]==20
          and n["source_reentry_plan"]==r["source_reentry_plan_max_120"]
          and states==r["article_intake_actions"] and match==0
          and r["operating_research_DB_merge"]=="NOT_RUN_RESEARCH_ISOLATED_SQLITE_ONLY"
          and r["research_fact_promotable_strict_pairs"]==r["LIVE_writes"]==
              r["production_data_branch_writes"]==r["production_sidecar_branch_writes"]==0
          and r["historical_511_published_record_count"]=="NOT_RECLASSIFIED",
          "SOURCE_FREE_AGGREGATE_REQUERY_MISMATCH")
    return {"status":"PASS_S6_316_SOURCE_FREE_RESEARCH_DB_FRESH_REQUERY",
            "articles":n["article_intake"],"hold_targets":n["target_holds"],
            "source_bound_facts":n["research_facts"],
            "planned_only":n["source_reentry_plan"],
            "strict_verified_pairs":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--join",type=Path)
    p.add_argument("--s5",type=Path)
    p.add_argument("--standard",type=Path)
    p.add_argument("--supplier",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        print("BCT_S6_316_DB_READBACK="+canon(fresh_readback(args.out)))
        return
    guard(all((args.join,args.s5,args.standard,args.supplier)),
          "ALL_FOUR_SEALED_SOURCE_FREE_INPUTS_REQUIRED")
    parents=validate_parents(args.join,args.s5,args.standard,args.supplier)
    oldids=read_previous_hashed_ids(args.join)
    raw=fetch_canonical_sqlite()
    with tempfile.TemporaryDirectory(prefix="bct-s6-316-canonical-") as t:
        rows,reviews,aux=read_canonical(raw,Path(t)/"canonical.sqlite3")
    intake,queue,review_counts=classify_316(rows,reviews,oldids,PINNED_CANONICAL_SHA)
    targets=combine_target_holds(args.s5)
    facts=combined_research_facts(args.standard,args.supplier,
                                   {x["target_id"] for x in targets})
    result=build_summary(intake,queue,review_counts,targets,facts,parents,aux)
    final=write_db(args.out,result,intake,queue,targets,facts)
    print("BCT_S6_316_ACTUAL_RESEARCH_INTAKE="+canon({
      "status":final["status"],
      "missing_articles":final["articles_without_prior_sidecar"],
      "work_states":final["article_intake_actions"],
      "rss_AI_separate_review":final["separate_rss_title_AI_annotations_in_missing_cohort"],
      "source_reentry_plan_only":final["source_reentry_plan_max_120"],
      "hold_targets":final["research_hold_registered_target_records"],
      "source_bound_research_facts":final["research_source_bound_original_fact_records"],
      "fact_event_groups":final["research_fact_event_groups"],
      "verified_eligible_pair":"NOT_EVALUATED",
      "operating_writes":0}),flush=True)

if __name__=="__main__":
    main()
