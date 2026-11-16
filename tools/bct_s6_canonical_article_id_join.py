"""S6 exact historical same-time canonical RSS SQLite versus sidecar results ID join.

The two immutable operating GitHub commit SHAs are the same pins successfully
read during the earlier S6 full-40-shard verification. Full article text and
private CPU state are never read, copied into artifacts or published.
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.request import Request,urlopen

from bct.objective_lock import stamp_export,require_objective
from bct_s6_full_sidecar_reconcile import (
    get_manifest,restore_exact,github_get,verify_git_blob,digest,canonical,HEX64,
    REPO,DATA_BRANCH,SIDE_BRANCH,
)

FORMAT="bct-s6-actual-rss-canonical-article-result-id-join-v1"
PINNED_DATA="a42a370044c3a5f8dc67af1faa1ec8bac6993e48"
PINNED_SIDE="873c2ab0df51d5cbd81cceb4575bf6d0e98d74d7"
PINNED_CANONICAL_SHA="8fe6199653b6190e984844fbd352be43b15cec917911ec54386822e16c6fde7e"
PINNED_RESULTS=10676
PINNED_RSS=10992
PINNED_S6_RUN=43846030879
PINNED_S6_ARTIFACT=14214378829
PINNED_S6_DIGEST="sha256:e289bdce90c734ca42cf869ac9ba280c0e859d4d32dce02b79e9bfa391eaf9a3"

def guard(ok,reason):
    if not ok:raise ValueError("BCT_S6_CANON_"+reason)

def validate_prior(old):
    require_objective(old)
    guard(old.get("format")=="bct-s6-exhaustive-sidecar-readonly-v1"
          and old.get("status")=="PASS_EXACT_FULL_SHARD_RECONSTRUCTION_AND_SOURCE_LINK_COUNT"
          and old.get("operating_heads")=={
              "data":PINNED_DATA,"future-bottleneck-data":PINNED_SIDE}
          and old.get("candidate_full_restore",{}).get("fetched_shards")==39
          and old.get("tracking_full_restore",{}).get("fetched_shards")==1
          and old.get("stored_records",{}).get("stored_result_document_ids")==PINNED_RESULTS
          and old.get("RSS_canonical_snapshot",{}).get("radar_items")==PINNED_RSS
          and old.get("RSS_canonical_snapshot",{}).get("canonical_sqlite_sha256_expected")==PINNED_CANONICAL_SHA
          and old.get("sidecar_branch_writes")==old.get("LIVE_writes")==0,
          "PRIOR_FULL_40_SHARD_REPORT_WRONG_GENERATION")
    return old

def get_state():
    wrapper=json.loads(github_get("/contents/state.json?ref="+PINNED_DATA,limit=1024*1024))
    guard(wrapper.get("encoding")=="base64" and wrapper.get("path")=="state.json",
          "PINNED_CANONICAL_STATE_NOT_VERIFIED")
    body=base64.b64decode(wrapper["content"])
    verify_git_blob(body,wrapper["sha"])
    s=json.loads(body)
    guard(s.get("radar_items")==PINNED_RSS and s.get("sha256")==PINNED_CANONICAL_SHA,
          "RSS_STATE_DIFFERENT_GENERATION")
    return s

def fetch_canonical_sqlite():
    """GitHub 'raw' API supports 1–100MB. Reject HTML or missing source data."""
    url=("https://api.github.com/repos/"+REPO+
         "/contents/canonical.sqlite3?ref="+PINNED_DATA)
    token=os.environ.get("GH_TOKEN","")
    guard(len(token)>20,"TOKEN_REQUIRED")
    req=Request(url,headers={
        "Accept":"application/vnd.github.raw+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"bct-s6-immutable-canonical-rss-readonly"})
    with urlopen(req,timeout=120) as resp:
        raw=resp.read(115*1024*1024+1)
    guard(len(raw)<=115*1024*1024,"CANONICAL_RAW_RESPONSE_EXCESSIVE")
    if raw.startswith(b"SQLite format 3\x00"):
        sqlite=raw
    else:
        try:
            value=json.loads(raw)
        except ValueError:
            raise ValueError("BCT_S6_CANON_GITHUB_RAW_NOT_SQLITE_OR_JSON") from None
        guard(isinstance(value,dict)
              and value.get("path")=="canonical.sqlite3"
              and value.get("size",0)<=90*1024*1024,
              "CANONICAL_CONTENTS_METADATA_INVALID")
        if value.get("encoding")=="base64":
            sqlite=base64.b64decode(value["content"])
        else:
            # The immutable Git blob endpoint is the only read fallback. Never
            # use a mutable branch URL, login bypass or query source material.
            blob=value.get("sha")
            guard(isinstance(blob,str) and len(blob)==40,"BLOB_FALLBACK_SHA_MISSING")
            doc=json.loads(github_get("/git/blobs/"+blob,limit=125*1024*1024))
            guard(doc.get("sha")==blob and doc.get("encoding")=="base64",
                  "LARGE_GIT_BLOB_NOT_VERIFIED")
            sqlite=base64.b64decode(doc["content"])
        verify_git_blob(sqlite,value["sha"])
    guard(sqlite.startswith(b"SQLite format 3\x00")
          and digest(sqlite)==PINNED_CANONICAL_SHA,
          "CANONICAL_RAW_SHA256_OR_FILE_HEADER_CHANGED")
    return sqlite

def rows_from_sqlite(raw,destination):
    destination=Path(destination)
    destination.write_bytes(raw)
    con=sqlite3.connect(destination.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    try:
        guard(con.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "CANONICAL_SQLITE_INTEGRITY_FAILURE")
        cols={row[1] for row in con.execute("PRAGMA table_info(radar_items)")}
        guard({"id","status"}.issubset(cols),"CANONICAL_RSS_ARTICLE_SCHEMA_MISMATCH")
        result=con.execute("SELECT id,status FROM radar_items").fetchall()
        guard(len(result)==PINNED_RSS and len({x[0] for x in result})==PINNED_RSS,
              "CANONICAL_RSS_ID_COUNT_OR_UNIQUENESS_MISMATCH")
        guard(all(isinstance(i,str) and i for i,s in result),"EMPTY_CANONICAL_RSS_ID")
        return dict(result)
    finally:
        con.close()

def join_ids(canonical_rows,candidate,source,prior):
    validate_prior(prior)
    results=candidate.get("results")
    guard(isinstance(results,dict) and len(results)==PINNED_RESULTS,
          "PINNED_RESULTS_DIFFERENT_GENERATION")
    mids=set(canonical_rows);rids=set(results)
    shared=mids&rids
    canonical_only=mids-rids
    result_only=rids-mids
    classes=Counter();status=Counter();mapping=[]
    for id in sorted(mids|rids):
        position=("BOTH" if id in shared else
                  "CANONICAL_ONLY" if id in canonical_only else "SIDECAR_ONLY")
        classes[position]+=1
        if position=="BOTH":
            state=(results[id].get("body_status") or "UNKNOWN")
            status[str(state)]+=1
        else:state=None
        mapping.append({"hashed_article_id":hashlib.sha256(id.encode()).hexdigest(),
                        "cohort_state":position,"sidecar_body_state":state,
                        "canonical_status":canonical_rows.get(id)})
    guard(sum(classes.values())==len(mids|rids)
          and classes["BOTH"]+classes["CANONICAL_ONLY"]==PINNED_RSS
          and classes["BOTH"]+classes["SIDECAR_ONLY"]==PINNED_RESULTS,
          "ARTICLE_ID_JOIN_CARDINALITY_CHANGED")
    summary=stamp_export({
        "format":FORMAT,
        "status":"PASS_PINNED_CANONICAL_SQLITE_AND_ALL_SIDECAR_ARTICLE_ID_JOIN",
        "snapshot_cutoff":"2026-11-16T10:08:00Z",
        "scope":"EXACT_PINNED_DATA_AND_FUTURE_BRANCH_GENERATION",
        "data_commit_sha":PINNED_DATA,
        "sidecar_commit_sha":PINNED_SIDE,
        "canonical_sqlite_sha256":PINNED_CANONICAL_SHA,
        "sidecar_reconstructed_document_sha256":source,
        "canonical_rss_ids":len(mids),
        "sidecar_result_ids":len(rids),
        "id_join_counts":dict(sorted(classes.items())),
        "matched_article_body_states":dict(sorted(status.items())),
        "row_joined_hashed_article_ids":len(mapping),
        "different_article_ID_populations_not_verified_shortage":True,
        "HOLD_pending_analysis_is_not_equivalent_to_missing_sidecar_record":True,
        "historical_dashboard_511_source":"SEPARATE_PUBLISHED_RESEARCH_RECORDS",
        "qualified_independent_supply_demand_pairs":"NOT_ESTABLISHED_BY_ID_JOIN",
        "private_epoch_writes":0,"canonical_writes":0,
        "sidecar_writes":0,"LIVE_writes":0,"dashboard_writes":0,
        "S6_full_evidence_original_pair_integrity":"NOT_EVALUATED",
        "next_gate":"VERIFY_SOURCE_BOUND_ARTICLE_EVENTS_AND_ELIGIBLE_SUPPLY_PAIRS_SEPARATELY",
        "forecast_accuracy":"UNVERIFIED",
    })
    return summary,mapping

def persist(output,summary,rows):
    output=Path(output)
    guard(not output.exists(),"OVERWRITE_EXISTING_LEDGER_FORBIDDEN")
    output.mkdir(parents=True)
    sql=output/"s6-article-id-join.sqlite3"
    with sqlite3.connect(sql) as c:
        c.execute("CREATE TABLE article_join(id_sha TEXT PRIMARY KEY,kind TEXT NOT NULL,"
                  "body_state TEXT,canonical_state TEXT)")
        for row in rows:
            c.execute("INSERT INTO article_join VALUES(?,?,?,?)",
                      (row["hashed_article_id"],row["cohort_state"],
                       row["sidecar_body_state"],row["canonical_status"]))
    data=dict(summary)
    data["sqlite_sha256"]=digest(sql.read_bytes())
    (output/"s6-article-id-join.json").write_text(canonical(data)+"\n")
    readback(output)
    return data

def readback(path):
    path=Path(path)
    s=json.loads((path/"s6-article-id-join.json").read_text())
    require_objective(s)
    sql=path/"s6-article-id-join.sqlite3"
    guard(digest(sql.read_bytes())==s["sqlite_sha256"],"SQLITE_MUTATED")
    with sqlite3.connect(sql.resolve().as_uri()+"?mode=ro",uri=True) as conn:
        guard(conn.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INTEGRITY")
        counts=dict(conn.execute("SELECT kind,COUNT(*) FROM article_join GROUP BY kind"))
        n=conn.execute("SELECT COUNT(*) FROM article_join").fetchone()[0]
    guard(counts==s["id_join_counts"] and n==s["row_joined_hashed_article_ids"]
          and s["canonical_writes"]==s["sidecar_writes"]==s["LIVE_writes"]==0
          and s["S6_full_evidence_original_pair_integrity"]=="NOT_EVALUATED",
          "FALSE_OR_OUTDATED_ARTICLE_ID_JOIN")
    return {"status":"PASS_PINNED_RSS_AND_SIDECAR_FRESH_SQLITE_ID_JOIN",
            "articles":s["canonical_rss_ids"],
            "results":s["sidecar_result_ids"],
            "matched":counts.get("BOTH",0),
            "missing_result":counts.get("CANONICAL_ONLY",0),
            "sidecar_only":counts.get("SIDECAR_ONLY",0)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.verify_only:
        print("BCT_S6_CANONICAL_JOIN_READBACK="+canonical(readback(a.output)))
        return
    guard(a.prior is not None,"PINNED_S6_PREDECESSOR_RECEIPT_REQUIRED")
    prior=json.loads(a.prior.read_text())
    validate_prior(prior)
    state=get_state()
    m,_=get_manifest("future-candidates.json",PINNED_SIDE)
    guard(m["document_sha256"]==prior["candidate_full_restore"]["full_document_sha256"],
          "PINNED_SIDECAR_PARENT_DOCUMENT_CHANGED")
    results,receipt=restore_exact(m,workers=5)
    print("BCT_S6_PINNED_ID_SOURCE_RESTORED="+canonical({
        "shards":receipt["fetched_shards"],"hash":receipt["full_document_sha256"],
        "results":len(results["results"])}),flush=True)
    raw=fetch_canonical_sqlite()
    with tempfile.TemporaryDirectory(prefix="bct-s6-canonical-join-") as temp:
        rows=rows_from_sqlite(raw,Path(temp)/"canonical.sqlite3")
    report,linked=join_ids(rows,results,m["document_sha256"],prior)
    written=persist(a.output,report,linked)
    print("BCT_S6_PINNED_CANONICAL_ID_JOIN="+canonical({
      "status":written["status"],"counts":written["id_join_counts"],
      "canonical_sha":written["canonical_sqlite_sha256"],
      "all_result_shards_verified":receipt["fetched_shards"],
      "historical_511_separate":True,"qualified_pairs":written["qualified_independent_supply_demand_pairs"],
      "operating_writes":0}),flush=True)
if __name__=="__main__":
    main()
