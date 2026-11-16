"""S6 root-cause audit of the ACTUAL deployed public BCT Pages 511 evidence count.

Pinned GitHub Actions Pages artifact, not a guessed screenshot or older summary.
No archive extraction, source text publication, model calls or operating writes.
Research/sector rows and CPU product detail pages are distinct evidence units.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tarfile

from bct.objective_lock import stamp_export,require_objective

VERSION="bct-s6-pages-511-rootcause-v1"
SHA64=re.compile(r"^[0-9a-f]{64}$")
CATEGORY_COUNT={"reviewed":23,"structured":211,"discovery":277,
                "cpu_product":1186,"reported":6}
RUN_ID=43838794301
ARTIFACT_ID=14211394848
ARTIFACT_DIGEST="sha256:641cf9c02359db448a34e02f35e9a58b1d72453ee4be8514b053e39a25368316"

def canon(o):
    return json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
def sha(data):
    return hashlib.sha256(data if isinstance(data,bytes) else data.encode("utf-8")).hexdigest()
def require(ok,code):
    if not ok:raise ValueError("S6_511_"+code)

def audit_counts(build,dashboard,categories,ids,detail_ids,total_bytes):
    counts=dashboard.get("counts") or {}
    records=dashboard.get("records")
    require(isinstance(records,list) and len(records)==511
            and counts.get("evidence")==511 and len({x.get("id") for x in records})==511,
            "HISTORICAL_511_RECORD_ID_INTEGRITY")
    c=Counter(x.get("category") for x in records)
    require(c=={"reviewed":23,"structured":211,"discovery":277},
            "HISTORICAL_CATEGORY_SUM_MISMATCH")
    require(categories==CATEGORY_COUNT,"PUBLISHED_DETAIL_CATEGORY_1703")
    require(sum(categories.values())==1703
            and build.get("evidence_count")==1703
            and build.get("evidence_bytes")==total_bytes,
            "PUBLISHED_DETAIL_FILE_INVENTORY_MISMATCH")
    require(len(ids)==len(set(ids))==1703
            and set(x["id"] for x in records).issubset(ids)
            and set(x["id"] for x in records).issubset(detail_ids),
            "DASHBOARD_RECORDS_NOT_PUBLISHED_DETAIL_FILES")
    ranked=dashboard.get("sector_rankings") or {}
    live=dashboard.get("sector_rankings_live") or {}
    require(ranked.get("count_kind")==
            "SOURCE_LINKED_RESEARCH_RECORDS_NOT_VERIFIED_SHORTAGES"
            and ranked.get("ranked_record_count")==508
            and ranked.get("unclassified_count")==3
            and sum(x["evidence_count"] for x in ranked.get("rows",[]))==508,
            "HISTORICAL_RANK_SOURCE_NOT_508")
    require(live.get("ranked_record_count")==520
            and live.get("new_original_verified")==12
            and live.get("historical_source_rows")==508
            and sum(x["evidence_count"] for x in live.get("rows",[]))==520
            and live.get("no_verified_supply_shortage_promoted") is True,
            "NEW_ORIGINALS_ARE_NOT_MARKET_SHORTAGES")
    backlog=dashboard.get("source_backlog") or {}
    require(backlog.get("historical_rank_input_count")==511
            and backlog.get("rank_input_not_increased_by_rss") is True
            and backlog.get("audit_matches_live_sidecar") is False,
            "511_RANK_IS_HISTORICAL_INPUT_NOT_RECENT_ARTICLE_COUNT")
    require(build.get("rss_article_count")==10992
            and build.get("site_type")=="PUBLIC_STATIC_READ_ONLY"
            and build.get("new_ai_calls")==0
            and build.get("source_branch")=="codex/bct-v4-integration"
            and build.get("code_commit")=="ce1c28ce20ea0dbccaef14794a03e81f0061eec3",
            "PUBLIC_PAGES_BUILD_SOURCE_IDENTITY_CHANGED")
    require(dashboard.get("historical_data_at")=="2026-10-14T23:16:13.592709+00:00"
            and build.get("historical_data_at")==dashboard["historical_data_at"],
            "HISTORICAL_RANK_GENERATION_DATE_CHANGED")
    require(counts.get("future_candidates")=={"S1":0,"S2":0,"S3":0}
            and all(x.get("is_future_candidate") is False for x in records),
            "FALSE_POSITIVE_MARKET_PROMOTION")
    return stamp_export({
        "format":VERSION,
        "status":"PASS_ACTUAL_PUBLISHED_511_HISTORICAL_RANK_ROOTCAUSE",
        "published_build_generated_at":build["generated_at"],
        "dashboard_data_at":dashboard["data_at"],
        "historical_rank_input_last_updated_at":dashboard["historical_data_at"],
        "published_source_code_branch":build["source_branch"],
        "published_source_code_commit":build["code_commit"],
        "historical_dashboard_record_count":len(records),
        "historical_evidence_breakdown":dict(sorted(c.items())),
        "historical_ranked_sector_rows":508,
        "historical_unclassified_records":3,
        "published_detailed_evidence_files":1703,
        "published_detail_file_breakdown":dict(sorted(categories.items())),
        "published_extra_detail_files_not_historical_rank_rows":1703-511,
        "latest_rss_article_count_in_published_build":build["rss_article_count"],
        "live_overlay_sector_ranked_rows":520,
        "live_overlay_new_publisher_verified_unpaired":12,
        "historical_rank_input_not_increased_by_RSS":True,
        "different_unit_511_vs_1703_vs_10992":True,
        "source_rank_includes_unverified_discovery":True,
        "qualified_independent_supply_demand_pairs":"NOT_PROVEN_BY_PUBLIC_LINKS",
        "automatically_promoted_shortage_candidates":0,
        "next_action":"S6_RECONCILE_CURRENT_CANONICAL_SQLITE_WITH_ALL_STORED_ARTICLE_IDS",
        "operating_DB_writes":0,"LIVE_writes":0,"dashboard_deployed":False,
        "forecast_accuracy":"UNVERIFIED",
        "source_run_id":RUN_ID,"source_artifact_id":ARTIFACT_ID,
        "source_artifact_digest":ARTIFACT_DIGEST,
    })

def audit_tar(file):
    file=Path(file)
    require(file.is_file() and file.stat().st_size>10000,"PAGES_TAR_NOT_PRESENT")
    with tarfile.open(file,mode="r:") as tar:
        members=tar.getmembers()
        files={m.name:m for m in members if m.isfile()}
        def read(name,limit):
            key="./"+name
            require(key in files and files[key].size<=limit,"PUBLISHED_ASSET_UNAVAILABLE")
            return tar.extractfile(files[key]).read()
        raw=read("api/dashboard.json",10*1024*1024)
        build=json.loads(read("build-manifest.json",1024*1024))
        require(sha(raw)==build.get("dashboard_sha256"),
                "DASHBOARD_BUILD_CONTENT_DIGEST_CHANGED")
        dashboard=json.loads(raw)
        details=[m for m in members if m.isfile() and
                 m.name.startswith("./api/evidence/") and m.name.endswith(".json")]
        categories=Counter();ids=set();detail_ids=set();total_bytes=0
        for m in details:
            require(m.size<150000 and m.name.count("/")==3,
                    "UNSAFE_OR_OVERSIZE_PUBLISHED_DETAIL")
            fid=m.name.split("/")[-1][:-5]
            require(SHA64.fullmatch(fid) and fid not in ids,
                    "EVIDENCE_FILE_ID_INVALID_OR_DUPLICATE")
            ids.add(fid)
            b=tar.extractfile(m).read()
            total_bytes+=len(b)
            try:row=json.loads(b)
            except ValueError:raise ValueError("S6_511_NON_JSON_EVIDENCE_FILE") from None
            require(row.get("id")==fid,"EVIDENCE_FILE_RECORD_ID_MISMATCH")
            detail_ids.add(fid)
            categories[row.get("category")]+=1
        return audit_counts(build,dashboard,categories,ids,detail_ids,total_bytes)

def write(out,record):
    out=Path(out)
    require(not out.exists(),"OUTPUT_EXISTS")
    out.mkdir(parents=True)
    sql=out/"published-511-sourcefree.sqlite3"
    with sqlite3.connect(sql) as db:
        db.execute("CREATE TABLE proof(key TEXT PRIMARY KEY,sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        for k,v in sorted(record.items()):
            if k in ("objective_version","objective_sha256"):continue
            p=canon(v)
            db.execute("INSERT INTO proof VALUES(?,?,?)",(k,sha(p),p))
    data=dict(record)
    data["sqlite_sha256"]=sha(sql.read_bytes())
    (out/"published-511-reconciliation.json").write_text(canon(data)+"\n")
    requery(out)
    return data

def requery(out):
    out=Path(out)
    record=json.loads((out/"published-511-reconciliation.json").read_text())
    require_objective(record)
    sql=out/"published-511-sourcefree.sqlite3"
    require(sha(sql.read_bytes())==record["sqlite_sha256"],"SQLITE_SHA_MISMATCH")
    with sqlite3.connect(sql.resolve().as_uri()+"?mode=ro",uri=True) as db:
        require(db.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INVALID")
        rows=db.execute("SELECT key,sha256,payload FROM proof ORDER BY key").fetchall()
    for key,h,p in rows:
        require(sha(p)==h and json.loads(p)==record[key],"PUBLISHED_PROOF_RECORD_CHANGED")
    require(record["historical_dashboard_record_count"]==511
            and record["published_detailed_evidence_files"]==1703
            and record["live_overlay_new_publisher_verified_unpaired"]==12
            and record["automatically_promoted_shortage_candidates"]==0
            and record["operating_DB_writes"]==record["LIVE_writes"]==0,
            "UNAUTHORIZED_PUBLISHED_COUNT_PROMOTION")
    return {"status":"PASS_PUBLIC_511_SQLITE_FRESH_REQUERY",
            "historical_records":record["historical_dashboard_record_count"],
            "detail_files":record["published_detailed_evidence_files"],
            "live_overlay":record["live_overlay_sector_ranked_rows"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--site-tar",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.verify_only:
        print("BCT_S6_511_REQUERY="+canon(requery(a.out)))
        return
    require(a.site_tar is not None,"PAGES_TAR_REQUIRED")
    report=write(a.out,audit_tar(a.site_tar))
    print("BCT_S6_511_ROOT_CAUSE="+canon({
        "status":report["status"],
        "historical_511":report["historical_dashboard_record_count"],
        "breakdown":report["historical_evidence_breakdown"],
        "historical_rank_at":report["historical_rank_input_last_updated_at"],
        "published_detail_files":report["published_detailed_evidence_files"],
        "detail_types":report["published_detail_file_breakdown"],
        "new_originals_overlay":report["live_overlay_new_publisher_verified_unpaired"],
        "overlaid_rank_rows":report["live_overlay_sector_ranked_rows"],
        "current_RSS":report["latest_rss_article_count_in_published_build"],
        "qualified_pairs":report["qualified_independent_supply_demand_pairs"],
        "production_writes":0}),flush=True)

if __name__=="__main__":
    main()
