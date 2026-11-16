"""BCT S6 full, exact operating sidecar shard readback and evidence-unit audit.

The source of truth is a pair of immutable GitHub commit SHAs. Download and
verify ALL manifest shards, reconstruct the exact original JSON byte digest,
and compute only source-free statistics. Source records are transient in memory
and NEVER included in an artifact, log or promoted LIVE record.

This does not certify original article bodies or independent demand/supply
pairs; a stored screenshot/URL or evidence snippet alone does not establish one.
"""
import argparse
import base64
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,urlunsplit
from urllib.request import Request,urlopen

from bct.future_github import assemble,MANIFEST_FORMAT,SHARD_FORMAT,MAX_SHARD_BYTES
from bct.objective_lock import stamp_export,require_objective

FORMAT="bct-s6-exhaustive-sidecar-readonly-v1"
REPO="irewon1-lgtm/bottleneck-control-tower"
SIDE_BRANCH="future-bottleneck-data"
DATA_BRANCH="data"
HEX40=re.compile(r"^[a-f0-9]{40}$")
HEX64=re.compile(r"^[a-f0-9]{64}$")
BANNED={"body","article_html","original_text","private_token","raw_original","source_quote"}
PRIOR_S6_FORMAT="bct-s6-readonly-manifest-intake-v1"
FILE_PATHS=("future-candidates.json","future-tracking.json")
ALLOWED_ROLES={"DEMAND","SUPPLY","RELIEF","TRACKED_CHANGE","CONSTRAINT",
               "TIMING","CAPACITY_LEAD_TIME"}
MAX_BLOB_JSON=16*1024*1024+8192
MAX_CANONICAL_SQLITE=90*1024*1024

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False)
def digest(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode("utf-8")).hexdigest()
def guard(ok,reason):
    if not ok:raise ValueError("BCT_S6_FULL_"+reason)

def github_get(path,*,accept="application/vnd.github+json",limit=MAX_BLOB_JSON):
    token=os.getenv("GH_TOKEN") or ""
    guard(len(token)>20,"GITHUB_READ_TOKEN_REQUIRED")
    url="https://api.github.com/repos/"+REPO+path
    req=Request(url,headers={
        "Accept":accept,"Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"bct-s6-bounded-shard-proof"})
    for attempt in range(3):
        try:
            with urlopen(req,timeout=65) as resp:
                raw=resp.read(limit+1)
                guard(len(raw)<=limit,"GITHUB_RESPONSE_SIZE_EXCEEDED")
                return raw
        except HTTPError as exc:
            # Never evade access controls; retries only for proven transient
            # service errors, with a bounded count.
            if exc.code not in (500,502,503,504) or attempt==2:
                raise RuntimeError("GITHUB_READ_HTTP_"+str(exc.code)) from None
        except (TimeoutError,URLError) as exc:
            if attempt==2:raise RuntimeError("GITHUB_READ_TRANSIENT_EXHAUSTED") from None
        time.sleep(attempt+1)
    raise RuntimeError("GITHUB_READ_UNREACHABLE")

def branch_head(branch):
    guard(branch in (SIDE_BRANCH,DATA_BRANCH),"UNEXPECTED_BRANCH")
    value=json.loads(github_get("/git/ref/heads/"+branch))
    sha=value.get("object",{}).get("sha")
    guard(isinstance(sha,str) and HEX40.fullmatch(sha),"INVALID_BRANCH_HEAD")
    return sha

def verify_git_blob(raw,gitsha):
    actual=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    guard(actual==gitsha,"GIT_BLOB_CONTENT_MISMATCH")
    return raw

def get_manifest(path,commit):
    guard(path in FILE_PATHS and HEX40.fullmatch(commit),"UNPINNED_MANIFEST_REQUEST")
    value=json.loads(github_get("/contents/"+path+"?ref="+commit,limit=2*1024*1024))
    guard(value.get("path")==path and value.get("encoding")=="base64"
          and HEX40.fullmatch(value.get("sha","")),"MANIFEST_WRAPPER_INVALID")
    raw=base64.b64decode(value["content"],validate=False)
    verify_git_blob(raw,value["sha"])
    m=json.loads(raw)
    validate_manifest(m,path)
    return m,{"path":path,"blob_sha1":value["sha"],
              "manifest_sha256":digest(raw),"reconstructed_sha256":m["document_sha256"],
              "generation_shards":len(m["shards"]),"branch_sha":commit}

def validate_manifest(m,path):
    guard(m.get("format")==MANIFEST_FORMAT,"MANIFEST_FORMAT_CHANGED")
    guard(HEX64.fullmatch(m.get("document_sha256","")),"MANIFEST_DIGEST_INVALID")
    fields=m.get("fields");parts=m.get("shards");counts=m.get("item_counts")
    guard(type(fields)==list and type(parts)==list and type(counts)==dict
          and len(parts)>0 and len(parts)<=80
          and len(fields)==len(counts)
          and len(set(f.get("name") for f in fields))==len(fields),
          "MANIFEST_FIELD_OR_SHARD_STRUCTURE")
    guard(set(f.get("name") for f in fields)==set(counts),"SHARD_COUNT_KEYS_DIFFER")
    guard(all(type(n) is int and n>0 for n in counts.values())
          and sum(counts.values())==m.get("total_item_count"),
          "WRONG_MANIFEST_ITEM_COUNTS")
    stem=path[:-5]
    for i,p in enumerate(parts,1):
        expected=f"{stem}.shards/{m['document_sha256']}/{stem}.part-{i:03}.json"
        guard(type(p)==dict and p.get("path")==expected
              and type(p.get("item_count")) is int and p["item_count"]>0
              and HEX40.fullmatch(p.get("git_sha",""))
              and HEX64.fullmatch(p.get("sha256","")),
              "SHARD_PATH_OR_HASH_UNPINNED")
    guard(sum(x["item_count"] for x in parts)==m["total_item_count"],
          "SHARD_ITEM_TOTAL_NOT_MATCHED")
    return True

def read_immutable_shard(part):
    b=json.loads(github_get("/git/blobs/"+part["git_sha"],limit=MAX_BLOB_JSON))
    guard(b.get("sha")==part["git_sha"] and b.get("encoding")=="base64",
          "GITHUB_SHARD_WRAPPER_INVALID")
    raw=base64.b64decode(b["content"],validate=False)
    guard(0<len(raw)<=MAX_SHARD_BYTES and digest(raw)==part["sha256"],
          "SHARD_SHA_OR_SIZE_CHANGED")
    verify_git_blob(raw,part["git_sha"])
    return raw

def restore_exact(m,*,workers=5):
    """Fetch each immutable GitHub blob once; verify exact source digest via assembly."""
    guard(1<=workers<=8,"EXCESSIVE_PARALLEL_READS")
    chunks=[None]*len(m["shards"])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        task_to_i={pool.submit(read_immutable_shard,p):i
                   for i,p in enumerate(m["shards"])}
        for task in as_completed(task_to_i):
            chunks[task_to_i[task]]=task.result()
    raw_by_sha={p["git_sha"]:chunks[i] for i,p in enumerate(m["shards"])}
    # Project's own unmodified source-restoration routine verifies:
    # shard body digest, format/record counts/order, complete document digest.
    document=assemble(m,lambda part:raw_by_sha[part["git_sha"]])
    guard(set(document)==set(m["item_counts"]),"FULL_DOCUMENT_FIELD_MISMATCH")
    return document,{"fetched_shards":len(chunks),
                     "fetched_compressed_bytes":sum(len(x) for x in chunks),
                     "full_document_sha256":m["document_sha256"],
                     "all_manifest_counts_verified":True,
                     "all_record_keys_and_order_verified":True}

def public_url(raw):
    if not isinstance(raw,str) or len(raw)>4096:return None
    try:
        p=urlsplit(raw)
        if p.scheme not in ("http","https") or not p.hostname:return None
        return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or "/",
                            p.query,p.fragment))
    except ValueError:
        return None

def evidence_document_counts(candidate):
    result=candidate.get("results")
    hypotheses=candidate.get("hypotheses")
    events=candidate.get("events")
    guard(type(result)==type(hypotheses)==type(events)==dict,
          "UNEXPECTED_SIDECAR_DOCUMENT_SHAPE")
    evidence_roles=Counter();states=Counter();source_presence=Counter()
    ids=set(result);urls=Counter();bodies=Counter()
    with_evidence=0;with_both=0;not_matching_key=0;origin_complete=0
    provisional=[];exact_refs=0;missing_refs=0
    for key,r in result.items():
        guard(isinstance(key,str) and type(r)==dict,"BAD_RESULT_RECORD")
        if r.get("id") not in (key,None):not_matching_key+=1
        states[str(r.get("body_status") or "UNKNOWN")]+=1
        url=public_url(r.get("origin_url")) or public_url(r.get("url"))
        if url:urls[url]+=1
        h=r.get("current_body_sha256") or r.get("body_sha256")
        if isinstance(h,str) and HEX64.fullmatch(h):bodies[h]+=1
        if (r.get("provenance_verified") is True and
            r.get("publication_verified") is True and url and h and
            r.get("origin_publisher") and r.get("published_at")):
            origin_complete+=1
        ev=r.get("evidence")
        if type(ev)==dict:
            roles={k for k,v in ev.items() if v not in (None,[],"",{})}
            if roles:with_evidence+=1
            if {"DEMAND","SUPPLY"}.issubset(roles):with_both+=1
            for role in roles:evidence_roles[str(role)]+=1
        if r.get("candidate") is True:source_presence["candidate_flag_true"]+=1
        if r.get("final_bottleneck") is True:source_presence["final_flag_true"]+=1
    for hypothesis in hypotheses.values():
        if not isinstance(hypothesis,dict):continue
        current=hypothesis.get("current") or {}
        refs=current.get("evidence") or []
        if type(refs)!=list:continue
        for ref in refs:
            if type(ref)!=dict:continue
            doc_id=ref.get("document_id")
            if isinstance(doc_id,str):
                exact_refs+=1
                if doc_id not in ids:missing_refs+=1
    for ev in events.values():
        if not isinstance(ev,dict):continue
        docs=ev.get("documents")
        if isinstance(docs,list):
            for d in docs:
                if isinstance(d,str):
                    exact_refs+=1
                    if d not in ids:missing_refs+=1
    guard(not_matching_key==0,"RESULT_RECORD_SOURCE_ID_COLLISION")
    return {
      "stored_result_document_ids":len(ids),
      "body_status_counts":dict(sorted(states.items())),
      "records_with_role_tagged_evidence_not_qualified_pairs":with_evidence,
      "records_with_both_demand_and_supply_tags_not_independent":with_both,
      "role_tagged_document_occurrences":dict(sorted(evidence_roles.items())),
      "provenance_plus_publication_flagged_originals_not_full_audit":origin_complete,
      "unique_result_original_urls":len(urls),
      "result_url_repeat_excess_records":sum(c-1 for c in urls.values()),
      "distinct_stored_body_hashes":len(bodies),
      "body_sha_repeat_excess_records":sum(c-1 for c in bodies.values()),
      "records_without_public_url":len(ids)-sum(urls.values()),
      "records_without_body_version_sha256":len(ids)-sum(bodies.values()),
      "candidate_flagged_results_not_strict_qualified":source_presence["candidate_flag_true"],
      "final_bottleneck_flagged_results_not_strict_qualified":source_presence["final_flag_true"],
      "hypothesis_and_event_document_references_checked":exact_refs,
      "missing_referenced_result_ids":missing_refs,
      "hypothesis_records_not_qualified_pairs":len(hypotheses),
      "signal_event_records_not_independent_pairs":len(events),
      "qualified_independent_pairs":"NOT_DERIVABLE_FROM_ROLE_TAGS",
    }

def one_target_links(target,baseline=None):
    """Mirror docs/view-model.js evidence(...) per-target unique href behavior."""
    seen=set()
    def add(raw):
        url=public_url(raw if isinstance(raw,str) else
                       raw.get("url") if isinstance(raw,dict) else None)
        if url:seen.add(url)
    history=target.get("history") or []
    for record in reversed(history):
        if not isinstance(record,dict):continue
        for raw in record.get("sources") or []:add(raw)
        comparisons=record.get("comparison_inputs") or {}
        if isinstance(comparisons,dict):
            for val in comparisons.values():
                if not isinstance(val,dict):continue
                for ref in val.get("evidence") or []:
                    if isinstance(ref,dict):add(ref.get("url"))
    if isinstance(baseline,dict):
        for ref in baseline.get("sources") or []:add(ref)
    return seen

def tracking_counts(tracking,verified):
    targets=tracking.get("targets")
    guard(type(targets)==list and len(targets)==22,"EXPECTED_22_TRACKED_TARGETS")
    known=set();allurls=Counter();per_target={}
    base={x["id"]:x for x in (verified.get("items") or []) if isinstance(x,dict) and x.get("id")}
    for t in targets:
        guard(type(t)==dict and isinstance(t.get("id"),str)
              and t["id"] not in known,"DUPLICATE_TRACKING_TARGET")
        known.add(t["id"])
        urls=one_target_links(t,base.get(t["id"]))
        per_target[t["id"]]={"distinct_link_urls":len(urls),
                            "history_records":len(t.get("history") or [])}
        allurls.update(urls)
    guard(not set(base).difference(known),"VERIFIED_BASELINE_TARGET_MISSING")
    summed=sum(z["distinct_link_urls"] for z in per_target.values())
    return {
        "registered_target_ids":len(known),
        "unique_target_link_url_pairs":summed,
        "unique_source_urls_across_all_targets":len(allurls),
        "cross_target_repeated_url_pair_excess":summed-len(allurls),
        "per_target_source_url_counts":dict(sorted(per_target.items())),
        "recorded_link_urls_do_not_prove_full_body_or_pair":True,
    }

def audit(candidate,tracking,baseline,heads,manifest_proofs,restore_proofs,state=None):
    guard(all(HEX40.fullmatch(heads[k]) for k in (SIDE_BRANCH,DATA_BRANCH)),
          "UNPINNED_BRANCH_HEADS")
    cm,tm=manifest_proofs
    cp,tp=restore_proofs
    guard(cm["reconstructed_sha256"]==cp["full_document_sha256"]
          and tm["reconstructed_sha256"]==tp["full_document_sha256"]
          and cm["generation_shards"]==cp["fetched_shards"]
          and tm["generation_shards"]==tp["fetched_shards"],
          "PROOF_RESTORED_GENERATION_MISMATCH")
    guard(candidate.get("objective_version")=="bct-objective-1"
          and tracking.get("version")==1,"CANDIDATE_OBJECTIVE_OR_TRACKING_FORMAT")
    require_objective(candidate)
    ev=evidence_document_counts(candidate)
    tgt=tracking_counts(tracking,baseline)
    guard(ev["stored_result_document_ids"]==cm["manifest_result_count"]
          and len(candidate["hypotheses"])==cm["manifest_hypothesis_count"]
          and tgt["registered_target_ids"]==tm["manifest_targets_count"],
          "FULL_RESTORED_COUNTS_INCONSISTENT")
    # Keep all URL metrics disjoint: sector "publisher counts" from UI RSS
    # are NOT target-link URL pairs, and neither is an independent fact.
    side={"data":heads[DATA_BRANCH],"future-bottleneck-data":heads[SIDE_BRANCH]}
    report=stamp_export({
        "format":FORMAT,
        "status":"PASS_EXACT_FULL_SHARD_RECONSTRUCTION_AND_SOURCE_LINK_COUNT",
        "research_scope":"EXACT_TWO_PINNED_SIDECARS_PLUS_22_TRACKED_TARGETS",
        "operating_heads":side,
        "candidate_manifest_proof":cm,
        "tracking_manifest_proof":tm,
        "candidate_full_restore":cp,
        "tracking_full_restore":tp,
        "stored_records":ev,
        "target_source_links":tgt,
        "RSS_canonical_snapshot":state or {"status":"NOT_READ_YET"},
        "published_511_reproduced":tgt["unique_target_link_url_pairs"]==511,
        "published_511_basis":"TARGET_LINK_URL_PAIRS_NOT_INDEPENDENT_ORIGINALS",
        "published_511_verification_scope":"REPRODUCIBLE_FROM_CURRENT_TRACKING_IF_TRUE",
        "same_original_multi_target_dedup_not_supply_demand_evidence":True,
        "canonical_data_branch_writes":0,"sidecar_branch_writes":0,
        "private_epoch_writes":0,"LIVE_writes":0,"rank_writes":0,
        "entire_RSS_corpus_semantic_reanalysis":"NOT_PERFORMED",
        "qualified_independent_supply_demand_pairs":"NOT_PROVEN_BY_SHARD_LINKS",
        "S6_full_operating_research_DB_integration":"NOT_RUN",
        "next_gate":"S6_COMPARE_CANONICAL_SQLITE_DOCUMENT_IDS_AND_VERIFIED_ORIGINAL_FACT_LOCATORS",
        "forecast_accuracy":"UNVERIFIED",
    })
    return report

def save(path,report):
    path=Path(path)
    guard(not path.exists(),"NO_OVERWRITE")
    path.mkdir(parents=True)
    db=path/"s6-sidecar-derived.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE proofs(name TEXT PRIMARY KEY, record_sha256 TEXT NOT NULL, payload TEXT NOT NULL)")
        for name,val in sorted(report.items()):
            if name in ("objective_version","objective_sha256"):continue
            payload=canonical(val)
            conn.execute("INSERT INTO proofs VALUES(?,?,?)",(name,digest(payload),payload))
    record=dict(report)
    record["sqlite_sha256"]=digest(db.read_bytes())
    (path/"s6-full-shard-sourcefree.json").write_text(canonical(record)+"\n")
    fresh_readback(path)
    return record

def fresh_readback(path):
    path=Path(path)
    d=json.loads((path/"s6-full-shard-sourcefree.json").read_text())
    require_objective(d)
    db=path/"s6-sidecar-derived.sqlite3"
    guard(digest(db.read_bytes())==d.get("sqlite_sha256"),"SQLITE_SHA_MISMATCH")
    with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True) as c:
        guard(c.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_BAD")
        rows=c.execute("SELECT name,record_sha256,payload FROM proofs ORDER BY name").fetchall()
    for name,check,payload in rows:
        guard(digest(payload)==check
              and json.loads(payload)==d[name],"CORRUPT_SOURCE_FREE_PROOF")
    guard(d.get("status")=="PASS_EXACT_FULL_SHARD_RECONSTRUCTION_AND_SOURCE_LINK_COUNT"
          and d.get("sidecar_branch_writes")==d.get("LIVE_writes")==d.get("rank_writes")==0
          and d.get("S6_full_operating_research_DB_integration")=="NOT_RUN",
          "UNAUTHORIZED_INTEGRATION_CLAIM")
    return {"status":"PASS_FULL_SHARD_SOURCE_FREE_FRESH_SQLITE_READBACK",
            "fields":len(rows),
            "results":d["stored_records"]["stored_result_document_ids"],
            "source_links":d["target_source_links"]["unique_target_link_url_pairs"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--verified-baseline",type=Path,
                   default=Path("docs/verified-bottlenecks.json"))
    p.add_argument("--verify-only",action="store_true")
    p.add_argument("--workers",type=int,default=5)
    a=p.parse_args()
    if a.verify_only:
        print("BCT_S6_FULL_REQUERY="+canonical(fresh_readback(a.output)),flush=True)
        return
    heads={SIDE_BRANCH:branch_head(SIDE_BRANCH),DATA_BRANCH:branch_head(DATA_BRANCH)}
    print("BCT_S6_SHARD_SNAPSHOT_PINNED="+canonical(heads),flush=True)
    manifests=[];manifest_proofs=[];restore_proofs=[]
    for name in FILE_PATHS:
        manifest,proof=get_manifest(name,heads[SIDE_BRANCH])
        proof["manifest_result_count"]=manifest["item_counts"].get("results") if name.startswith("future-candidates") else None
        proof["manifest_hypothesis_count"]=manifest["item_counts"].get("hypotheses") if name.startswith("future-candidates") else None
        proof["manifest_targets_count"]=manifest["item_counts"].get("targets") if name.startswith("future-tracking") else None
        manifests.append(manifest)
        manifest_proofs.append(proof)
    full=[]
    for i,m in enumerate(manifests):
        doc,receipt=restore_exact(m,workers=a.workers)
        full.append(doc);restore_proofs.append(receipt)
        print("BCT_S6_SHARD_FULL_RESTORED="+canonical({
           "source":FILE_PATHS[i],"sha":m["document_sha256"],
           "exact_shards":receipt["fetched_shards"],
           "all_counts_verified":True}),flush=True)
    baseline=json.loads(a.verified_baseline.read_text())
    stateobj=json.loads(github_get("/contents/state.json?ref="+heads[DATA_BRANCH],limit=1024*1024))
    guard(stateobj.get("encoding")=="base64","CANONICAL_STATE_NOT_BASE64")
    raw=base64.b64decode(stateobj["content"])
    verify_git_blob(raw,stateobj["sha"])
    state=json.loads(raw)
    guard(type(state.get("radar_items")) is int and state["radar_items"]>0
          and HEX64.fullmatch(state.get("sha256","")),"CANONICAL_SNAPSHOT_NOT_PINNED")
    canon_state={"status":"PINNED_STATE_MANIFEST_NOT_DB_ROWS",
                 "radar_items":state["radar_items"],
                 "canonical_sqlite_sha256_expected":state["sha256"],
                 "state_file_blob_sha1":stateobj["sha"],
                 "full_sqlite_ID_join":"NOT_RUN_IN_SHARD_ONLY_GATE"}
    guard(branch_head(SIDE_BRANCH)==heads[SIDE_BRANCH] and
          branch_head(DATA_BRANCH)==heads[DATA_BRANCH],
          "OPERATING_REFS_CHANGED_DURING_SHARD_READ")
    report=audit(full[0],full[1],baseline,heads,manifest_proofs,restore_proofs,canon_state)
    saved=save(a.output,report)
    print("BCT_S6_FULL_SHARD_EVIDENCE_RECONCILE="+canonical({
        "status":saved["status"],
        "results":saved["stored_records"]["stored_result_document_ids"],
        "hypotheses":saved["stored_records"]["hypothesis_records_not_qualified_pairs"],
        "signal_events":saved["stored_records"]["signal_event_records_not_independent_pairs"],
        "target_link_pairs":saved["target_source_links"]["unique_target_link_url_pairs"],
        "unique_urls_across_targets":saved["target_source_links"]["unique_source_urls_across_all_targets"],
        "published_511_reproduced":saved["published_511_reproduced"],
        "rss_state_articles":saved["RSS_canonical_snapshot"]["radar_items"],
        "shards":sum(x["fetched_shards"] for x in restore_proofs),
        "eligible_supply_demand_pairs":saved["qualified_independent_supply_demand_pairs"],
        "production_writes":0}),flush=True)

if __name__=="__main__":
    main()
