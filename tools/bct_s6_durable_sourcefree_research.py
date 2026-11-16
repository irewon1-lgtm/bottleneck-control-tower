"""BCT S6 append-only durable research ledger from two real source-free CI receipts.

Persist the already verified 316 RSS-only cases, 60 actual source attempts,
22 HOLD targets, 20 original source facts and 147 source-bound research hints.
The output contains NO article bodies/URLs and cannot create qualified pairs.

The only permitted destination is a NEW independent research-owned branch;
production RSS, future sidecar, existing published rank and LIVE remain intact.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from bct.objective_lock import stamp_export,require_objective

FORMAT="bct-s6-durable-sourcefree-research-ledger-v1"
PREPARED_316="bct-s6-316-rss-source-bound-intake-v1"
ACTUAL_60="bct-s6-60-real-original-reentry-v1"
ARTIFACTS={
    "s6_316":{"run_id":43857086796,"head_sha":"1c266920f8db2e9588342305670d7e5f6efaba9c",
        "id":14220458504,
        "digest":"sha256:542d38565e7bf13051fb11e0c3f5b8d9de6f7c16b2d7a27c55d1f2d480e6c5eb",
        "file":"s6-research-sourcefree.sqlite3","summary":"s6-research-summary.json"},
    "s6_60":{"run_id":43861667664,"head_sha":"edbdf61ea877eaa586af43b4bdc9c19dec02e8ad",
        "id":14224420540,
        "digest":"sha256:07584445de593e7d65923d6e17cbd39513bc6f6c8bd6df41e796de1b42e052e3",
        "file":"s6-60-sourcefree.sqlite3","summary":"s6-60-execution.json"}
}
COUNT={"article_intake":316,"source_reentry_plan":60,"target_holds":22,
       "research_facts":20,"source_attempts":60,"source_bound_hints":147}
PUBLISH_BRANCH="research/bct-s6-sourcefree-ledger-20261116"
NO_RAW=frozenset({"body","html","url","title","text","article_text","source_quote",
                  "article_body","raw","private_cache","private_token"})
HEX64=re.compile(r"^[a-f0-9]{64}$")
def canonical(o):
    return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def sha(b):
    return hashlib.sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
def require(ok,err):
    if not ok:raise ValueError("BCT_S6_LEDGER_"+err)

def unpack_single(path,expected):
    path=Path(path)
    root=path if path.is_dir() else None
    if root:
        files={n:(root/n).read_bytes() for n in (expected["file"],expected["summary"])}
    else:
        with zipfile.ZipFile(path) as zipped:
            names=zipped.namelist()
            require(set(names)=={expected["file"],expected["summary"]},
                    "SOURCE_ARTIFACT_CONTAINS_EXTRA_OR_UNEXPECTED_FILES")
            files={n:zipped.read(n) for n in names}
    summary=json.loads(files[expected["summary"]])
    require_objective(summary)
    require(sha(files[expected["file"]])==summary.get("sqlite_sha256",
           summary.get("research_sqlite_sha256")),"ORIGINAL_RESEARCH_DB_SHA_CHANGED")
    return files[expected["file"]],summary

def read_db(file_bytes,scope,tmp):
    path=tmp/(scope+".sqlite3")
    path.write_bytes(file_bytes)
    db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    require(db.execute("PRAGMA integrity_check").fetchone()==("ok",),
            "PARENT_SQLITE_INTEGRITY_"+scope)
    return db

def verify_origins(a,b):
    require(a.get("format")==PREPARED_316 and
            a.get("articles_without_prior_sidecar")==316 and
            a.get("research_hold_registered_target_records")==22 and
            a.get("research_source_bound_original_fact_records")==20 and
            a.get("source_reentry_plan_max_120")==60 and
            a.get("research_fact_promotable_strict_pairs")==0 and
            a.get("operating_research_DB_merge")=="NOT_RUN_RESEARCH_ISOLATED_SQLITE_ONLY"
            and a.get("LIVE_writes")==0 and a.get("source_article_body_or_url_exported") is False,
            "S6_316_SOURCE_RECEIPT_INVALID")
    require(b.get("format")==ACTUAL_60 and
            b.get("planned_selected")==b.get("actual_eligible_source_attempts")==60 and
            b.get("skipped_existing_current_sidecar_record")==0 and
            b.get("actual_acquired_body_states")=={"FULL":24,"PARTIAL":22,"UNAVAILABLE":14}
            and b.get("new_strict_original_verified")==18 and
            b.get("new_source_bound_research_fact_hints")==147 and
            b.get("input_S6_research_sqlite_sha256")==a.get("sqlite_sha256") and
            b.get("existing_operating_CAS_mutations")==b.get("research_pair_admitted")==
                b.get("forecast_candidate_or_LIVE_promotions")==0 and
            b.get("original_source_bodies_or_urls_persisted") is False,
            "S6_60_ACTUAL_ORIGINAL_RECEIPT_INVALID")
    require(a["canonical_sqlite_sha256"]==b["sample_historical_RSS_snapshot_sha256"],
            "DIFFERENT_RSS_COHORT_GENERATION")
    return True

TABLES={
    "article_intake":("s6_316","article_intake","id_sha","payload","sha"),
    "source_reentry_plan":("s6_316","source_reentry_plan","id_sha",None,None),
    "target_holds":("s6_316","target_holds","target_id","payload","sha"),
    "research_facts":("s6_316","research_facts","fact_sha","payload","sha"),
    "source_attempts":("s6_60","source_attempts","id_sha","payload","sha"),
    "source_bound_hints":("s6_60","source_bound_hints","fact_sha","payload","payload_sha"),
}

def collect(parent316,parent60,tmp):
    bytes316,proof316=unpack_single(parent316,ARTIFACTS["s6_316"])
    bytes60,proof60=unpack_single(parent60,ARTIFACTS["s6_60"])
    verify_origins(proof316,proof60)
    sources={"s6_316":read_db(bytes316,"316",tmp),
             "s6_60":read_db(bytes60,"60",tmp)}
    records={}
    try:
        for name,(origin,table,keyfield,payloadfield,hashfield) in TABLES.items():
            db=sources[origin]
            cols=[x[1] for x in db.execute("PRAGMA table_info("+table+")")]
            require(keyfield in cols and
                    (payloadfield is None or {payloadfield,hashfield}.issubset(cols)),
                    "PARENT_SQLITE_SCHEMA_"+name)
            selected=(keyfield+","+payloadfield+","+hashfield) if payloadfield else "*"
            rows=db.execute("SELECT "+selected+" FROM "+table).fetchall()
            require(len(rows)==COUNT[name] and
                    len({r[0] for r in rows})==COUNT[name],
                    "PARENT_SOURCE_ROW_COUNT_"+name)
            if payloadfield:
                for key,payload,h in rows:
                    require(sha(payload)==h,"PARENT_RECORD_SHA_"+name)
                    item=json.loads(payload)
                    require(not NO_RAW.intersection(item),"RAW_ARTICLE_LEAK_"+name)
                    if name=="article_intake":
                        require(item["id_sha256"]==key and
                                item["qualifying_source_evidence_count"]==0 and
                                item["original_source_url_or_title_exported"] is False,
                                "ARTICLE_ALREADY_PROMOTED")
                    elif name=="target_holds":
                        require(item["target_id"]==key and item["disposition"]=="HOLD" and
                                item["candidate_promotion"] is False,
                                "TARGET_HOLD_CHANGED")
                    elif name=="research_facts":
                        require(item["fact_key_sha256"]==key and
                                item["strict_original_pair_eligible"] is False and
                                item["annual_same_scope_unreserved_supply"]=="UNKNOWN",
                                "ORIGINAL_FACT_FALSELY_PROMOTED")
                    elif name=="source_attempts":
                        require(item["id_sha256"]==key and
                                item["auto_promotions"]==item["auto_retries_added_to_operating_DB"]==0 and
                                item["source_date_or_original_text_exported"] is False,
                                "SOURCE_ATTEMPT_FALSE_SUCCESS")
                    elif name=="source_bound_hints":
                        require(item["fact_sha256"]==key and
                                item["strict_economic_pair_admitted"] is False and
                                item["classification"]==
                                    "SOURCE_BOUND_RESEARCH_HINT_NOT_INDEPENDENT_ELIGIBLE_PAIR",
                                "SOURCE_HINT_FALSELY_PROMOTED")
            records[name]=rows
    finally:
        for source in sources.values():source.close()
    original_articles={r[0] for r in records["article_intake"]}
    plan_ids={r[0] for r in records["source_reentry_plan"]}
    attempts={r[0]:json.loads(r[1]) for r in records["source_attempts"]}
    holds={r[0] for r in records["target_holds"]}
    require(plan_ids==set(attempts) and plan_ids.issubset(original_articles) and
            "unobligated-haleu-us-qualified-supply" in holds,
            "S6_PLAN_AND_ACTUAL_RESULTS_DIFFER")
    hints=Counter()
    for key,payload,h in records["source_bound_hints"]:
        item=json.loads(payload)
        owner=item["id_sha256"]
        require(owner in attempts and attempts[owner]["verified_public_original"] is True and
                item["body_sha256"]==attempts[owner]["hash_version"] and
                isinstance(item["span_sha256"],str) and HEX64.fullmatch(item["span_sha256"]),
                "HINT_NOT_BOUND_TO_VERIFIED_ORIGINAL")
        hints[owner]+=1
    require(all(attempts[k]["new_source_bound_research_fact_hints"]==hints[k]
                for k in attempts),"SOURCE_HINTS_PER_ATTEMPT_MISMATCH")
    status=Counter(x["source_body_status"] for x in attempts.values())
    require(dict(status)==proof60["actual_acquired_body_states"] and
            sum(a["verified_public_original"] for a in attempts.values())==18,
            "SOURCE_ATTEMPT_STATISTICS_CHANGED")
    causal=Counter(json.loads(p)["causal_event"] for _,p,h in records["research_facts"])
    require(dict(causal)==proof316["research_fact_event_groups"],"CAUSAL_DEDUP_CHANGED")
    return records,proof316,proof60

def materialize(parent316,parent60,out):
    out=Path(out)
    require(not out.exists(),"OUTPUT_OVERWRITE_FORBIDDEN")
    out.mkdir(parents=True)
    records,a,b=collect(parent316,parent60,out)
    dbfile=out/"research-sourcefree.sqlite3"
    with sqlite3.connect(dbfile) as con:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("CREATE TABLE article_intake(id_sha TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        con.execute("CREATE TABLE source_reentry_plan(id_sha TEXT PRIMARY KEY REFERENCES article_intake(id_sha),ordinal INTEGER NOT NULL UNIQUE)")
        con.execute("CREATE TABLE target_holds(target_id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        con.execute("CREATE TABLE research_facts(fact_sha TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        con.execute("CREATE TABLE source_attempts(id_sha TEXT PRIMARY KEY REFERENCES article_intake(id_sha),payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        con.execute("CREATE TABLE source_bound_hints(fact_sha TEXT PRIMARY KEY,id_sha TEXT NOT NULL REFERENCES source_attempts(id_sha),payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        for name,rows in records.items():
            if name=="source_reentry_plan":
                con.executemany("INSERT INTO source_reentry_plan VALUES(?,?)",rows)
            elif name=="source_bound_hints":
                for key,payload,h in rows:
                    item=json.loads(payload)
                    con.execute("INSERT INTO source_bound_hints VALUES(?,?,?,?)",
                                (key,item["id_sha256"],h,payload))
            else:
                table=name
                # Parent SELECT reads key,payload,sha; durable table stores
                # key,sha,payload. Preserve hashes byte-for-byte.
                con.executemany("INSERT INTO "+table+" VALUES(?,?,?)",
                                [(key,h,payload) for key,payload,h in rows])
        require(con.execute("PRAGMA foreign_key_check").fetchall()==[],
                "SQLITE_CROSS_TABLE_FOREIGN_KEY_MISMATCH")
    reported=stamp_export({
       "format":FORMAT,
       "scope":"REAL_SOURCE_FREE_RESEARCH_LEDGER_NO_LIVE_OR_RANK_PROMOTION",
       "session6_status":"DURABLE_RESEARCH_DB_PUBLISHABLE_NOT_FULL_PHYSICAL_PAIR_COMPLETION",
       "source_artifacts":ARTIFACTS,
       "parent_316_sqlite_sha256":a["sqlite_sha256"],
       "parent_60_sqlite_sha256":b["research_sqlite_sha256"],
       "parent_article_snapshot_sha256":a["canonical_sqlite_sha256"],
       "source_counts":COUNT,
       "source_original_verified":18,
       "source_attempt_states":b["actual_acquired_body_states"],
       "source_bound_research_hints":147,
       "official_original_research_fact_codes":20,
       "registered_targets_preserved_hold":22,
       "article_s6_still_unattempted_in_this_snapshot":316-60,
       "strict_eligible_independent_pairs_admitted":0,
       "previous_public_rank_511":"HISTORICAL_NOT_UPDATED",
       "actual_rss_source_attempts":60,
       "current_operating_sidecar_latest_status":"NOT_RECHECKED_IN_RESEARCH_DB",
       "research_storage_branch":PUBLISH_BRANCH,
       "data_or_future_branch_writes":0,
       "LIVE_writes":0,"public_Pages_deploys":0,
       "forecast_accuracy":"UNVERIFIED",
       "next_gate":"S6_FINAL_SOURCE_INDEPENDENCE_AND_RESEARCH_DB_CAS_REQUERY_PLUS_REMAINING_256",
    })
    reported["sqlite_sha256"]=sha(dbfile.read_bytes())
    (out/"research-summary.json").write_text(canonical(reported)+"\n")
    readback(out)
    return reported

def readback(path):
    p=Path(path)
    s=json.loads((p/"research-summary.json").read_text())
    require_objective(s)
    dbfile=p/"research-sourcefree.sqlite3"
    require(sha(dbfile.read_bytes())==s.get("sqlite_sha256"),"DB_BYTES_CHANGED")
    with sqlite3.connect(dbfile.resolve().as_uri()+"?mode=ro",uri=True) as db:
        require(db.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INTEGRITY")
        require(db.execute("PRAGMA foreign_key_check").fetchall()==[],
                "SQLITE_FOREIGN_KEY_INTEGRITY")
        actual={t:db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                for t in COUNT}
        require(actual==COUNT==s["source_counts"],"STORED_SOURCE_COUNT_CHANGED")
        for t,cols in (("article_intake",("id_sha","payload_sha256","payload")),
                       ("target_holds",("target_id","payload_sha256","payload")),
                       ("research_facts",("fact_sha","payload_sha256","payload")),
                       ("source_attempts",("id_sha","payload_sha256","payload")),
                       ("source_bound_hints",("fact_sha","payload_sha256","payload"))):
            for pk,h,payload in db.execute("SELECT "+",".join(cols)+" FROM "+t):
                require(sha(payload)==h and isinstance(json.loads(payload),dict),
                        "STORED_ROW_SHA_OR_JSON_CHANGED_"+t)
        verified=db.execute(
            "SELECT COUNT(*) FROM source_attempts "
            "WHERE json_extract(payload,'$.verified_public_original')=1").fetchone()[0]
        hints=db.execute(
            "SELECT COUNT(*) FROM source_bound_hints f "
            "JOIN source_attempts a ON a.id_sha=f.id_sha "
            "WHERE json_extract(a.payload,'$.verified_public_original')=1").fetchone()[0]
        holds=db.execute("SELECT COUNT(*) FROM target_holds "
                         "WHERE json_extract(payload,'$.disposition')='HOLD'").fetchone()[0]
        disallowed=db.execute("SELECT COUNT(*) FROM research_facts "
              "WHERE json_extract(payload,'$.strict_original_pair_eligible')<>0").fetchone()[0]
    require(verified==18 and hints==147 and holds==22 and disallowed==0 and
            s["strict_eligible_independent_pairs_admitted"]==0 and
            s["data_or_future_branch_writes"]==s["LIVE_writes"]==s["public_Pages_deploys"]==0,
            "STORED_FALSE_ELIGIBLE_PAIR_OR_METRICS")
    return {"status":"PASS_DURABLE_S6_RESEARCH_SQLITE_FRESH_READBACK",
            "articles":actual["article_intake"],
            "source_attempts":actual["source_attempts"],
            "verified_public_originals":verified,
            "source_bound_hints":hints,
            "HOLD_targets":holds,
            "research_fact_codes":actual["research_facts"],
            "qualified_pairs":0,
            "sqlite_sha256":s["sqlite_sha256"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--parent316",type=Path)
    p.add_argument("--parent60",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        print("BCT_S6_DURABLE_READBACK="+canonical(readback(args.out)),flush=True);return
    require(args.parent316 and args.parent60,"ACTUAL_SOURCE_FREE_PARENT_PROOFS_REQUIRED")
    a=materialize(args.parent316,args.parent60,args.out)
    print("BCT_S6_DURABLE_RESEARCH_PREPARED="+canonical({
       "status":"PASS_REAL_SOURCE_FREE_APPEND_ONLY_PREPARED",
       "sqlite_sha256":a["sqlite_sha256"],
       "originals_verified":a["source_original_verified"],
       "attempted":a["actual_rss_source_attempts"],
       "target_holds":a["registered_targets_preserved_hold"],
       "source_facts":a["official_original_research_fact_codes"],
       "source_hints":a["source_bound_research_hints"],
       "eligible_pairs":0}),flush=True)
if __name__=="__main__":
    main()
