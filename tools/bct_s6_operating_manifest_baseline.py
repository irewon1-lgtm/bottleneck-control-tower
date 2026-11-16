"""Session 6: immutable operating-branch manifest baseline; no shard/evidence promotion.

Reads GitHub API file wrappers pinned to exact branch HEAD commit SHAs and the
authenticated previous S5 22-target HOLD review. Does not call the model,
parse original text, alter branches, or claim 10k+ article evidence coverage.
"""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from bct.objective_lock import require_objective,stamp_export

VERSION="bct-s6-readonly-manifest-intake-v1"
S5_FORMAT="bct-s5-22-target-closed-disposition-v1"
S5_HANDOFF="bct-s6-research-intake-pending-v1"
BRANCHES=("data","future-bottleneck-data")
SOURCES={
    "precursor_index":("data","precursor-index.json"),
    "v4_acquisition":("data","v4-public/acquisition.json"),
    "v4_research":("data","v4-public/research.json"),
    "future_candidates_manifest":("future-bottleneck-data","future-candidates.json"),
    "future_tracking_manifest":("future-bottleneck-data","future-tracking.json"),
}
HEX40=re.compile(r"^[0-9a-f]{40}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")

def canon(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

def sha256(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()

def fail(code):
    raise ValueError("BCT_S6_"+code)

def check(ok,code):
    if not ok:fail(code)

def validate_s5(parent,handoff):
    require_objective(parent);require_objective(handoff)
    check(parent.get("format")==S5_FORMAT
          and parent.get("cohort_disposition")=="PASS_ALL_22_TARGETS_EXPLICITLY_CATEGORIZED"
          and parent.get("targets_total")==parent.get("targets_reviewed")==22
          and parent.get("qualified")==parent.get("rejected")==0
          and parent.get("hold")==22
          and parent.get("LIVE_candidates_created")==parent.get("production_research_DB_writes")==0
          and parent.get("production_rank_writes")==0
          and parent.get("full_10k_article_research_audit")=="NOT_PERFORMED",
          "PARENT_S5_SOURCE_PROOF_INVALID")
    check(handoff.get("format")==S5_HANDOFF
          and handoff.get("S5_scoped_22_target_review")=="PASS"
          and handoff.get("eligible_to_integrate_verified_pairs")==0
          and handoff.get("hold_cases_for_research_DB")==22
          and handoff.get("promotion_allowed") is False
          and handoff.get("production_DB_write_allowed") is False
          and handoff.get("S6_full_database_integration")=="NOT_RUN"
          and handoff.get("parent_sha256")==sha256(canon(parent))
          and handoff.get("source_sqlite_sha256")==parent.get("sqlite_sha256")
          and handoff.get("source_cases_sha256")==parent.get("cases_sha256"),
          "S5_S6_HANDOFF_BINDING_CHANGED")
    return True

def parse_api_wrapper(wrapper,path,sha):
    check(isinstance(wrapper,dict) and wrapper.get("path")==path
          and wrapper.get("encoding")=="base64"
          and isinstance(wrapper.get("content"),str)
          and re.fullmatch(r"[0-9a-f]{40}",str(wrapper.get("sha",""))),
          "PUBLIC_GITHUB_FILE_WRAPPER_BAD")
    try:
        raw=base64.b64decode(wrapper["content"],validate=False)
    except (ValueError,TypeError) as exc:
        fail("CONTENT_DECODE_FAILED")
    gitblob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
    check(gitblob==wrapper["sha"],"GITHUB_SOURCE_BLOB_HASH_MISMATCH")
    try:
        data=json.loads(raw)
    except ValueError:
        fail("NONJSON_SOURCE_MANIFEST")
    check(type(data)==dict,"SOURCE_MANIFEST_NOT_MAPPING")
    return data,{
        "path":path,"git_blob_sha1":gitblob,"source_sha256":sha256(raw),
        "branch_commit_sha":sha,"source_size":len(raw),
        "source_type":"PUBLIC_BRANCH_MANIFEST_NOT_VERIFIED_PHYSICAL_EVIDENCE"}

def audit(sources,heads,s5,s5_handoff):
    validate_s5(s5,s5_handoff)
    check(set(heads)==set(BRANCHES)
          and all(isinstance(v,str) and HEX40.fullmatch(v) for v in heads.values())
          and len(set(heads.values()))==len(BRANCHES),"BAD_OPERATING_BRANCH_REF")
    check(set(sources)==set(SOURCES),"MISSING_OPERATING_METADATA_SOURCE")
    actual={};records=[]
    for key,(branch,path) in SOURCES.items():
        value,proof=parse_api_wrapper(sources[key],path,heads[branch])
        actual[key]=value
        records.append({"name":key,"branch":branch,**proof})
    f=actual["future_candidates_manifest"]
    t=actual["future_tracking_manifest"]
    a=actual["v4_acquisition"];r=actual["v4_research"]
    p=actual["precursor_index"]

    check(f.get("format")==t.get("format")=="bct-sharded-sidecar-v1"
          and all(type(q.get("item_counts")) is dict for q in (f,t))
          and isinstance(f.get("shards"),list)
          and isinstance(t.get("shards"),list),"SHARDED_MANIFEST_INCOMPLETE")
    check(type(t["item_counts"].get("targets")) is int
          and t["item_counts"]["targets"]==22,"CANONICAL_TARGET_COUNT_MISMATCH")
    for k in ("results","hypotheses","events"):
        check(type(f["item_counts"].get(k)) is int
              and f["item_counts"][k]>=0,
              "SHARD_MANIFEST_TYPED_ITEM_COUNT_INVALID")
    for q in (f,t):
        check(HEX64.fullmatch(str(q.get("document_sha256","")))
              and q.get("total_item_count")==sum(q["item_counts"].values())
              and all(isinstance(s.get("path"),str)
                      and HEX64.fullmatch(str(s.get("sha256","")))
                      and type(s.get("item_count")) is int
                      and s["item_count"]>0 for s in q["shards"]),
              "SHARDED_MANIFEST_INTEGRITY_FIELDS_MISSING")
    check(a.get("format")=="bct-public-acquisition-1"
          and p.get("format")=="bct-new-precursor-collection-v1"
          and r.get("format")=="bct-public-research-1"
          and all(v.get("objective_version")=="bct-objective-1"
                  for v in (a,p,r)),
          "V4_PUBLIC_INPUT_VERSION_OR_OBJECTIVE")
    for q in (a,p,r):
        require_objective(q)
    check(p.get("independent_pair_count") in (0,None)
          and p.get("early_frozen")==0
          and a.get("counts",{}).get("new_verified_documents") is not None,
          "LATEST_PRECURSOR_INPUT_NOT_CONSISTENT")
    states=r.get("analysis",{}).get("states",{})
    check(all(type(v) is int and v>=0 for v in states.values()),
          "PUBLIC_RESEARCH_STATES_INVALID")
    review_count=sum(states.values())
    check(type(r.get("analysis",{}).get("trace_total")) is int
          and review_count==r["analysis"]["trace_total"],"PUBLIC_RESEARCH_STATES_INCONSISTENT")
    check(r.get("analysis",{}).get("trace_truncated") is True,
          "PUBLIC_TRACE_CANNOT_BE_ASSUMED_COMPLETE")
    candidate_counts={k:f["item_counts"][k] for k in ("results","hypotheses","events")}
    result=stamp_export({
      "format":VERSION,
      "decision":"PASS_OPERATING_BRANCH_METADATA_BASELINE_NOT_EVIDENCE_COUNT",
      "scope":"CURRENT_TWO_OPERATING_BRANCH_MANIFESTS_AND_S5_22_HOLD_HANDOFF_ONLY",
      "S5_held_targets":22,
      "S6_research_intake":"METADATA_BASELINE_COMPLETE_SHARD_EVIDENCE_RECONCILIATION_REQUIRED",
      "S6_full_operating_DB_integration":"NOT_RUN",
      "operating_branch_commit_shas":heads,
      "five_manifest_source_versions":records,
      "manifest_target_records":t["item_counts"]["targets"],
      "candidate_shard_manifest_counts":candidate_counts,
      "candidate_result_items_are_not_qualified_evidence":True,
      "candidate_shards_count":len(f["shards"]),
      "tracking_shards_count":len(t["shards"]),
      "candidate_manifest_document_sha256":f["document_sha256"],
      "tracking_manifest_document_sha256":t["document_sha256"],
      "data_precursor_new_verified_documents":p.get("new_verified_documents"),
      "data_precursor_unverified_source_holds":p.get("unverified_source_holds"),
      "data_precursor_independent_pairs":p.get("independent_pair_count"),
      "data_precursor_early_frozen":p.get("early_frozen"),
      "data_precursor_completed_at":p.get("completed_at"),
      "data_v4_public_read_states":states,
      "data_v4_public_trace_total":r["analysis"]["trace_total"],
      "data_v4_public_trace_truncated":True,
      "data_v4_public_producer_run_id":r.get("generation",{}).get("producer_run_id"),
      "data_v4_public_persisted_at":r.get("clocks",{}).get("persisted_at"),
      "data_v4_public_differs_from_new_private_epoch":True,
      "published_sector_evidence_511":"NOT_DETERMINABLE_FROM_MANIFESTS",
      "actual_qualified_independent_pairs":"NOT_EVALUATED_S6_OPERATING_SHARDS",
      "entire_10k_article_semantic_coverage":"NOT_AUDITED",
      "operating_data_branch_writes":0,"research_sidecar_writes":0,
      "LIVE_writes":0,"rank_promotions":0,
      "source_article_text_copied":False,
      "next_stage_gate":"S6_LOAD_EXACT_SHARDS_RECOUNT_DISTINCT_ARTICLE_AND_EVIDENCE_IDS_WITH_SOURCE_HASHES",
      "forecast_accuracy":"UNVERIFIED"})
    return result,records

def persist(path,report,records):
    path=Path(path)
    check(not path.exists(),"NO_OVERWRITE")
    path.mkdir(parents=True)
    db=path/"s6-index-metadata.sqlite3"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE files(name TEXT PRIMARY KEY,sha256 TEXT NOT NULL,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        for x in records:
            payload=canon(x)
            c.execute("INSERT INTO files VALUES(?,?,?,?)",
                      (x["name"],x["source_sha256"],sha256(payload),payload))
    out=dict(report)
    out["sqlite_sha256"]=sha256(db.read_bytes())
    out["recordset_sha256"]=sha256(canon(sorted(records,key=lambda x:x["name"])))
    (path/"s6-index-baseline.json").write_text(canon(out)+"\n")
    fresh_readback(path)
    return out

def fresh_readback(path):
    p=Path(path)
    report=json.loads((p/"s6-index-baseline.json").read_text())
    require_objective(report)
    f=p/"s6-index-metadata.sqlite3"
    check(sha256(f.read_bytes())==report["sqlite_sha256"],"SQLITE_BYTES_CHANGED")
    with sqlite3.connect(f.resolve().as_uri()+"?mode=ro",uri=True) as c:
        check(c.execute("PRAGMA integrity_check").fetchone()==("ok",),
              "SQLITE_CORRUPTION")
        rows=c.execute("SELECT name,sha256,payload_sha256,payload FROM files ORDER BY name").fetchall()
    check(len(rows)==5,"FIVE_OPERATING_MANIFEST_PROOFS_REQUIRED")
    records=[]
    for name,source_sha,payload_sha,payload in rows:
        check(sha256(payload)==payload_sha,"PER_RECORD_PAYLOAD_CHANGED")
        value=json.loads(payload)
        check(value["name"]==name and value["source_sha256"]==source_sha,
              "SOURCE_PROOF_REBOUND")
        records.append(value)
    check(sha256(canon(records))==report["recordset_sha256"]
          and report["manifest_target_records"]==22
          and report["candidate_result_items_are_not_qualified_evidence"] is True
          and report["published_sector_evidence_511"]=="NOT_DETERMINABLE_FROM_MANIFESTS"
          and report["S6_full_operating_DB_integration"]=="NOT_RUN"
          and report["operating_data_branch_writes"]==report["research_sidecar_writes"]==
              report["LIVE_writes"]==report["rank_promotions"]==0,
          "INCOMPLETE_OR_FALSE_EVIDENCE_COUNT")
    return {"status":"PASS_READONLY_FIVE_MANIFEST_SQLITE_REQUERY",
            "files":len(rows),"targets":22,
            "published_511":"NOT_DETERMINABLE_FROM_MANIFESTS"}

def main():
    q=argparse.ArgumentParser()
    q.add_argument("--sources",type=Path)
    q.add_argument("--s5",type=Path)
    q.add_argument("--s5-handoff",type=Path)
    q.add_argument("--out",type=Path,required=True)
    q.add_argument("--verify-only",action="store_true")
    args=q.parse_args()
    if args.verify_only:
        print("BCT_S6_INITIAL_REQUERY="+canon(fresh_readback(args.out)))
        return
    check(args.sources is not None and args.s5 is not None and
          args.s5_handoff is not None,"INPUTS_REQUIRED")
    sources={name:json.loads((args.sources/(name+".json")).read_text())
             for name in SOURCES}
    heads=json.loads((args.sources/"heads.json").read_text())
    s5=json.loads(args.s5.read_text())
    handoff=json.loads(args.s5_handoff.read_text())
    report,records=audit(sources,heads,s5,handoff)
    final=persist(args.out,report,records)
    print("BCT_S6_ACTUAL_INDEX_BASELINE="+canon({
       "status":final["decision"],
       "branch_shas":final["operating_branch_commit_shas"],
       "targets":final["manifest_target_records"],
       "shard_results_not_verified_evidence":final["candidate_shard_manifest_counts"]["results"],
       "shard_hypotheses_not_qualified":final["candidate_shard_manifest_counts"]["hypotheses"],
       "source_verified_new_documents_from_data":final["data_precursor_new_verified_documents"],
       "public_v4_read_states":final["data_v4_public_read_states"],
       "evidence_511":final["published_sector_evidence_511"],
       "S6_full_integration":final["S6_full_operating_DB_integration"],
       "next_gate":final["next_stage_gate"]}))
if __name__=="__main__":
    main()
