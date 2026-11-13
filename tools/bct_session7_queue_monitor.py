#!/usr/bin/env python3
"""BCT session7 CPU-only operational work queue. Zero article-body requests.

Makes all RSS article IDs visible with mutually exclusive acquisition, source
hold, and review work states. A ranked screening hint is not a verified shortage.
Old and new articles both receive bounded slots; source-confirmed/failed status
is never overwritten by a fresh keyword search.

Production source/DB/target state is never written by this reader.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import argparse
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from urllib.parse import urlsplit

from bct.future_bottleneck import screen
from bct.radar_signals import extract
from bct.future_github import assemble

ROLES=("DEMAND","SUPPLY","RELIEF")
PRIORITIES=("P1_MULTISIGNAL_METADATA","P2_TEXT_CUE","P3_BROAD_TEXT_CUE","P4_NO_METADATA_CUE")
LANES=("Q1_PRIOR_FULL_BODY_LEAD","Q2_PRIOR_PARTIAL_BODY_LEAD",
       "Q3_PRIOR_UNAVAILABLE_LEAD_HOLD","Q4_METADATA_SIGNAL_NEEDS_SOURCE",
       "Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING")
ACCESS_HOLDS=("HTTP_403","HTTP_401","HTTP_404","ACCESS_CHALLENGE",
              "PAYWALL_OR_LOGIN_PREVIEW","SOURCE_ACCESS_BLOCKED")

def git_bytes(ref,path):
    p=subprocess.run(["git","show",f"{ref}:{path}"],capture_output=True)
    if p.returncode:
        raise ValueError("PINNED_GIT_OBJECT_NOT_AVAILABLE:"+path)
    return p.stdout

def sha(raw):return hashlib.sha256(raw).hexdigest()

def iso(value):
    try:
        x=datetime.fromisoformat((value or "").replace("Z","+00:00"))
        return x.astimezone(timezone.utc) if x.tzinfo else None
    except (ValueError,TypeError,AttributeError):return None

def csv_cell(x):
    s="" if x is None else str(x)
    return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s

def physical_metadata(row):
    title=row.get("title") or ""
    description=row.get("snippet") or ""
    broad=screen(title+"\n"+description)
    narrow=extract(title,description)
    kinds=tuple(k for k in ROLES if k in broad.get("discovery_paths",[]))
    codes=sorted({r["signal"] for r in narrow})
    if len(kinds)>=2 and codes:prio=PRIORITIES[0]
    elif codes or len(kinds)>=2:prio=PRIORITIES[1]
    elif kinds:prio=PRIORITIES[2]
    else:prio=PRIORITIES[3]
    return kinds,codes,prio

def prior_body(record):
    if record is None:return "NOT_IN_SIDECAR"
    version=record.get("current_body_sha256") or record.get("body_sha256")
    snap=(record.get("versions") or {}).get(version,{}) if version else {}
    value=snap.get("body_status") or record.get("body_status") or "UNKNOWN"
    return "PARTIAL" if value=="BODY_OK" else value

def reasons(record):
    if not record:return ()
    ledger=(record.get("acquisition") or {}).get("versions",{})
    fingerprint=record.get("source_version") or record.get("fingerprint")
    current=ledger.get(fingerprint,{})
    latest=current.get("latest") or {}
    values=(record.get("reasons") or [])+(latest.get("reasons") or [])
    if record.get("reaccess_status"):values.append(str(record["reaccess_status"]))
    return tuple(dict.fromkeys(str(x) for x in values if x))

def classify(row,prior,asof):
    kinds,codes,priority=physical_metadata(row)
    body=prior_body(prior)
    candidate=bool(prior and prior.get("candidate") is True)
    old_decision=prior.get("decision","") if prior else ""
    if body=="FULL" and candidate and old_decision in ("CONTEXT_REVIEW","CANDIDATE_ONLY"):
        lane=LANES[0]
    elif body=="PARTIAL" and candidate:lane=LANES[1]
    elif body=="UNAVAILABLE" and candidate:lane=LANES[2]
    elif priority!=PRIORITIES[3]:lane=LANES[3]
    else:lane=LANES[4]
    host=urlsplit(row.get("url") or "").hostname
    valid_url=bool(host and urlsplit(row["url"]).scheme in ("http","https")
                   and not urlsplit(row["url"]).username
                   and not urlsplit(row["url"]).password)
    source_id=sha(((row["url"] or "")+(row.get("updated_at") or "")).encode())
    source_changed=bool(prior and prior.get("fingerprint")!=source_id)
    why=reasons(prior)
    attempts=int(prior.get("attempts") or 0) if prior else 0
    until=iso(prior.get("retry_after")) if prior else None
    blocked=any(any(reason.upper().startswith(code) for code in ACCESS_HOLDS) for reason in why)
    if not valid_url:
        action="HOLD_INVALID_SOURCE_URL"
    elif body=="FULL":
        action="REVIEW_VERIFIED_BODY_PROVENANCE" if candidate else "CHECK_NEGATIVE_FULL_BODY"
    elif body=="PARTIAL" and blocked and not source_changed:
        action="HOLD_PARTIAL_SOURCE_ACCESS"
    elif blocked and not source_changed:
        action="HOLD_SOURCE_ACCESS"
    elif attempts>=3 and not source_changed:
        action="HOLD_ATTEMPT_LIMIT"
    elif until and until>asof and not source_changed:
        action="WAIT_RETRY_AFTER"
    else:
        action="FETCH_OR_RECHECK_ORIGINAL"
    collected=iso(row.get("collected_at"))
    age=(asof-collected).total_seconds()/3600 if collected else None
    recency="RECENT_48H" if age is not None and 0<=age<=48 else "OLDER_OR_UNKNOWN"
    return {
        "article_id":row["id"],"source":row.get("source"),"url":row.get("url"),
        "published_at":row.get("published_at"),"collected_at":row.get("collected_at"),
        "source_fingerprint":source_id,
        "sidecar_record_present":prior is not None,
        "body_status":body,
        "prior_candidate_unverified":candidate,
        "prior_decision":old_decision or "UNKNOWN",
        "review_lane":lane,"metadata_priority":priority,
        "metadata_roles":"|".join(kinds),
        "narrow_signal_codes":"|".join(codes),
        "work_action":action,
        "recency_bucket":recency,
        "source_updated_since_old_screen":source_changed,
        "previous_attempts":attempts,
        "retry_after":prior.get("retry_after") if prior else "",
        "access_hold":blocked,
        "original_provenance_verified":bool(prior and prior.get("provenance_verified") is True),
        "publication_verified":bool(prior and prior.get("publication_verified") is True),
        "independent_supply_demand_pair_verified":False,
        "S1_S2_S3_verified_from_this_run":False
    }

def plan_work(items, *, budget=120, fresh_fraction=.4, max_host=6):
    if not 1<=budget<=300 or not 0<=fresh_fraction<=1 or max_host<1:
        raise ValueError("WORK_BUDGET_OUT_OF_BOUNDS")
    due=[x for x in items if x["work_action"]=="FETCH_OR_RECHECK_ORIGINAL"]
    score={lane:i for i,lane in enumerate(LANES)}
    prio={prio:i for i,prio in enumerate(PRIORITIES)}
    # New RSS items get bounded service, while old backlog always keeps slots.
    # A new item has never been labelled as "first seen today" without history.
    recent=sorted((x for x in due if x["recency_bucket"]=="RECENT_48H"),
        key=lambda x:(prio[x["metadata_priority"]],x["collected_at"] or "",x["article_id"]))
    old=sorted((x for x in due if x["recency_bucket"]!="RECENT_48H"),
        key=lambda x:(prio[x["metadata_priority"]],x["collected_at"] or "",x["article_id"]))
    recent_limit=round(budget*fresh_fraction)
    selected=[];selected_ids=set();hosts=Counter()
    def add_from(pool,limit):
        for x in pool:
            if len(selected)>=limit:break
            if x["article_id"] in selected_ids:continue
            host=(urlsplit(x["url"]).hostname or "").lower()
            if hosts[host]>=max_host:continue
            selected.append(x);selected_ids.add(x["article_id"]);hosts[host]+=1
    add_from(recent,recent_limit)
    add_from(old,budget)
    add_from(recent,budget)
    return selected

def reconcile(rows,sidecar,asof,*,budget=120):
    if asof.tzinfo is None:raise ValueError("ASOF_MUST_BE_TIMEZONE_AWARE")
    byid={row.get("id"):row for row in rows}
    if not rows or len(byid)!=len(rows) or None in byid:
        raise ValueError("RSS_ID_UNIQUE_NONEMPTY_REQUIRED")
    orphan=set(sidecar)-set(byid)
    if orphan:raise ValueError("SIDECAR_ORPHAN_UNHANDLED:"+str(len(orphan)))
    ledger=[classify(row,sidecar.get(row["id"]),asof) for row in rows]
    queue=plan_work(ledger,budget=budget)
    count=Counter(x["body_status"] for x in ledger)
    lane=Counter(x["review_lane"] for x in ledger)
    actions=Counter(x["work_action"] for x in ledger)
    recency=Counter(x["recency_bucket"] for x in ledger)
    if len(queue)!=len({x["article_id"] for x in queue}):
        raise ValueError("DUPLICATE_WORK_SELECTION")
    return ledger,queue,{
       "status":"PASS_READ_ONLY_QUEUE_RECONCILIATION",
       "scope":"ALL_ACTIVE_RSS_METADATA_AND_PREVIOUS_VERIFIED_BODY_RECEIPTS",
       "articles":len(rows),"prior_sidecar_results":len(sidecar),
       "sidecar_attached_articles":sum(x["sidecar_record_present"] for x in ledger),
       "articles_without_sidecar":sum(not x["sidecar_record_present"] for x in ledger),
       "body_counts":dict(count),"review_lanes":dict(lane),
       "work_actions":dict(actions),"recency_buckets":dict(recency),
       "waiting_fetch_or_recheck":actions["FETCH_OR_RECHECK_ORIGINAL"],
       "blocked_or_deferred":sum(v for k,v in actions.items() if k.startswith(("HOLD_","WAIT_"))),
       "selected_work_count":len(queue),
       "selected_recent":sum(x["recency_bucket"]=="RECENT_48H" for x in queue),
       "selected_older":sum(x["recency_bucket"]!="RECENT_48H" for x in queue),
       "selected_work_only_not_executed":True,
       "new_full_article_downloads":0,"source_API_calls":0,
       "candidate_promotions":0,
       "human_review_completions_created":0,
       "cost_USD":0
    }

def write_csv(path,rows,columns):
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        for x in rows:writer.writerow({k:csv_cell(x.get(k)) for k in columns})

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--data-sha",required=True)
    p.add_argument("--sidecar-sha",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--budget",type=int,default=120)
    args=p.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    state_bytes=git_bytes(args.data_sha,"state.json")
    state=json.loads(state_bytes)
    raw=git_bytes(args.data_sha,"canonical.sqlite3")
    if sha(raw)!=state["sha256"]:
        raise ValueError("CANONICAL_DB_STATE_SHA256_MISMATCH")
    temp=args.output/"_canonical.sqlite3"
    temp.write_bytes(raw)
    try:
        with sqlite3.connect("file:"+str(temp.resolve())+"?mode=ro&immutable=1",uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("CANONICAL_DB_CORRUPT")
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute(
                "SELECT id,source,url,title,snippet,published_at,collected_at,updated_at "
                "FROM radar_items WHERE status='active' ORDER BY collected_at,id")]
            total=db.execute("SELECT count(*) FROM radar_items").fetchone()[0]
        if len(rows)!=total or total!=state["radar_items"]:
            raise ValueError("CANONICAL_ACTIVE_COUNTS_NOT_EXHAUSTIVE")
        manifest=json.loads(git_bytes(args.sidecar_sha,"future-candidates.json"))
        if manifest.get("format")!="bct-sharded-sidecar-v1":
            raise ValueError("SIDECAR_MANIFEST_INVALID")
        verified=[0]
        def shard(x):
            raw=git_bytes(args.sidecar_sha,x["path"])
            verified[0]+=1
            return raw
        sidecar_doc=assemble(manifest,shard)
        if not isinstance(sidecar_doc.get("results"),dict):
            raise ValueError("SIDECAR_RESULTS_MISSING")
        now=datetime.now(timezone.utc)
        ledger,work,summary=reconcile(rows,sidecar_doc["results"],now,budget=args.budget)
        summary.update({
           "generated_at_utc":now.isoformat(),"canonical_data_sha":args.data_sha,
           "canonical_data_db_sha256":state["sha256"],"rss_run_id":state.get("run_id"),
           "sidecar_sha":args.sidecar_sha,
           "prior_sidecar_checked_at":sidecar_doc.get("summary",{}).get("checked_at"),
           "sidecar_shards_hash_verified":verified[0],
           "sidecar_manifest_sha256":manifest.get("document_sha256"),
           "processing_is_proven_only_by_existing_source_receipts":True
        })
        fields=list(ledger[0])
        write_csv(args.output/"articles_ledger.csv",ledger,fields)
        write_csv(args.output/"bounded_work_plan.csv",work,fields)
        (args.output/"queue_health.json").write_text(
            json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        md=["# BCT 세션 7 — 기존 RSS·신규기사 대기열 점검",
            "","**대기열 계획을 생성했을 뿐 기사 본문을 새로 처리한 것은 아닙니다.**",
            f"- 전수 확인: {len(ledger):,}건",
            f"- 기존 sidecar 연결: {summary['sidecar_attached_articles']:,}건, 미연결: {summary['articles_without_sidecar']:,}건",
            f"- 실제 본문 재확보 작업 후보: {summary['waiting_fetch_or_recheck']:,}건",
            f"- 접근 제한·재시도 제한으로 대기: {summary['blocked_or_deferred']:,}건",
            f"- 기존 본문 상태: {summary['body_counts']}",
            f"- 무료 CPU 다음 실행에 요청할 검토 순서: {len(work)}건 (최근 48시간 {summary['selected_recent']} / 기존 적체 {summary['selected_older']})",
            "","본문 FULL/원문 출처 검증/독립 수요·공급쌍/확정 병목은 각각 별도의 증거 요건이다.",
            "누락된 기사나 P4 신호 없는 기사를 영구 배제하지 않는다.",
            "기존 운영 Future workflow가 실제 본문 수집과 CAS 저장을 담당하며 이 모니터는 쓰지 않는다."]
        (args.output/"queue_readme_ko.md").write_text("\n".join(md)+"\n",encoding="utf-8")
        print("BCT_S7_QUEUE="+json.dumps(summary,ensure_ascii=False,sort_keys=True),flush=True)
    finally:
        temp.unlink(missing_ok=True)

if __name__=="__main__":
    main()
