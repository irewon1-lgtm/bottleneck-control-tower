#!/usr/bin/env python3
"""Session 6: exact-source-version, read-only cross-sector demand/supply audit.

Scope: the 45 VERIFIED_FULL publisher originals from the 302-doc frozen S5
snapshot. Reacquire ONLY these 45 (previous full bodies were not persisted).
Never equate publisher provenance with issuer-primary evidence.
The existing graph engine is used unchanged and its entire potentially
copyrighted graph never leaves this process; only short metadata receipts do.
"""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

from bct.future_bottleneck import fetch_capture
from bct.future_body import extract_document,access_failure
from bct import target_acquisition, precursor_collection
from bct import precursor_evidence_graph as evidence_graph
from bct import precursor_source_search as primary
from bct import forecast_discovery as strict

S5_ARTIFACT_RUN=43341520709
S5_ARTIFACT_ID=13999008324
EXPECTED_FULL_COUNT=45
MAX_WORKERS=4
REQUIRED_FIELDS=(
 "document_id","source_url","source_host","pilot_status",
 "body_sha256","provenance_verified"
)

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def h(raw):
    return hashlib.sha256(raw).hexdigest()

def safe_csv(v):
    if v is None:return ""
    text="|".join(str(x) for x in v) if isinstance(v,list) else str(v)
    if text.lstrip().startswith(("=","+","-","@","\t","\r")):return "'"+text
    return text

def read_frozen(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=302 or any(not set(REQUIRED_FIELDS)<=set(r) for r in rows):
        raise ValueError("SESSION5_RECONCILED_302_SCHEMA_OR_COUNT")
    if len({r["document_id"] for r in rows})!=302:
        raise ValueError("SESSION5_DUPLICATE_RSS_ARTICLE")
    full=[r for r in rows if r["pilot_status"]=="VERIFIED_FULL"]
    if len(full)!=EXPECTED_FULL_COUNT:
        raise ValueError("SESSION5_VERIFIED_FULL_45_EXPECTED")
    if any(r["provenance_verified"]!="True" or
           not re.fullmatch(r"[0-9a-f]{64}",r["body_sha256"] or "") or
           not r["source_url"].startswith(("https://","http://")) or
           (urlsplit(r["source_url"]).hostname or "").lower()!=r["source_host"].lower()
           for r in full):
        raise ValueError("SESSION5_VERIFIED_ORIGINAL_PROVENANCE_LOST")
    return sorted(full,key=lambda r:r["document_id"])

def result_stub(item):
    return {
      "document_id":item["document_id"],
      "source_url":item["source_url"],
      "source_host":item["source_host"],
      "old_body_sha256":item["body_sha256"],
      "current_body_sha256":None,
      "source_version_same":False,
      "reaccess":"NOT_STARTED",
      "status":"SOURCE_UNAVAILABLE",
      "issuer_primary_verified":False,
      "readable_event_count":0,
      "demand_events":0,"supply_events":0,"relief_events":0,
      "scope_complete_events":0,
      "qualified_supplier_events":0,
      "explicit_future_need_events":0,
      "first_blocker":"NOT_STARTED",
      "extraction_method":None
    }

def fetch_one(item,locks):
    """Fetch at most once; no retries or paywall bypass."""
    out=result_stub(item)
    try:
        host=out["source_host"]
        with locks[host]:
            data=fetch_capture(item["source_url"])
        if data.get("truncated"):
            out.update(reaccess="TRUNCATED",first_blocker="TRUNCATED_NEW_SOURCE_VERSION")
            return out,None
        extraction=extract_document(
            data["html"],http_status=data["status"],content_type=data["content_type"])
        out["extraction_method"]=extraction.get("extraction_method")
        if extraction["body_status"]!="FULL" or not extraction.get("body"):
            out.update(reaccess="NO_CURRENT_FULL_BODY",first_blocker="NO_CURRENT_FULL_BODY")
            return out,None
        body=extraction["body"]
        current=h(body.encode())
        out["current_body_sha256"]=current
        if current!=item["body_sha256"]:
            out.update(reaccess="SOURCE_VERSION_CHANGED",
                       first_blocker="BODY_HASH_DIFFERS_FROM_SESSION5_SNAPSHOT")
            return out,None
        out["source_version_same"]=True
        proof=target_acquisition.verify(data["raw"],item["source_url"],
                     data["final_url"],utc_now(),data["status"],data["content_type"])
        if (proof.get("provenance_verified") is not True
            or proof.get("body_sha256")!=current):
            out.update(reaccess="PROVENANCE_CHANGED",
                       first_blocker="CURRENT_SOURCE_IDENTITY_OR_DATE_UNVERIFIED")
            return out,None
        document={**proof,"document_id":item["document_id"]}
        document["provenance"]="PASS"
        document["provenance_verified"]=True
        structured=precursor_collection.structure(document,data["raw"],fresh=False)
        events=structured.get("precursor_events",[])
        out.update(reaccess="PASS_SAME_VERIFIED_BODY_VERSION",
                   status="SAME_VERSION_DOCUMENT_READ",
                   readable_event_count=len(events),
                   demand_events=sum(e.get("role")=="DEMAND" for e in events),
                   supply_events=sum(e.get("role")=="SUPPLY" for e in events),
                   relief_events=sum(e.get("role")=="RELIEF" for e in events),
                   scope_complete_events=sum(not e.get("missing_scope") for e in events),
                   qualified_supplier_events=sum(
                       e.get("role")=="SUPPLY" and e.get("qualified") is True
                       for e in events),
                   explicit_future_need_events=sum(
                       e.get("role")=="DEMAND" and
                       bool(e.get("future_period",{}).get("start") not in (None,"UNKNOWN"))
                       for e in events))
        primary_verified=primary.primary_origin(structured,events)
        out["issuer_primary_verified"]=primary_verified is True
        if not primary_verified:
            out["first_blocker"]="PUBLISHER_SOURCE_NOT_ISSUER_PRIMARY"
        elif not any(not e.get("missing_scope") for e in events):
            out["first_blocker"]="PRIMARY_BUT_TARGET_SCOPE_MISSING"
        else:
            out["first_blocker"]="PRIMARY_SCOPE_REQUIRES_OPPOSITE_EVIDENCE"
        return out,structured
    except Exception as exc:
        info=access_failure(exc)
        out.update(reaccess="FETCH_OR_PARSER_ERROR",
                   first_blocker="ACCESS_"+str(info.get("category")),
                   error_type=type(exc).__name__,
                   access_state=info.get("state"),
                   retryable=info.get("retryable"))
        return out,None

def graph_safe_summary(docs, *, now=None):
    """Existing graph is authoritative for source relation gates, not this wrapper."""
    if not docs:
        return {
            "graph_status":"NO_IMMUTABLE_VERIFIED_BODY_SNAPSHOT",
            "source_docs":0,"source_reference_checks":0,
            "graph_observations":0,"graph_issuer_evidence":0,
            "complete_target_events":0,"independent_demand_supply_pairs":0,
            "comparable_period_pairs":0,
            "potential_gaps":0,"backfill_protected_candidates":0,
            "pairs":[],"blocked_reasons":{}
        }
    # BACKFILL: re-acquired sources do not establish a 2026 LIVE first detection.
    graph=evidence_graph.analyze(docs,mode="BACKFILL",now=now or utc_now())
    if graph.get("version")!=evidence_graph.VERSION:
        raise ValueError("GRAPH_PROOF_VERSION_MISMATCH")
    pairs=[]
    for p in graph["pairs"]:
        if p.get("independent") is not True:
            raise ValueError("GRAPH_PAIR_IS_NOT_INDEPENDENT")
        target=next((x for x in graph["targets"]
                     if x.get("target_id")==p.get("target_id")),None)
        scope=target.get("scope",{}) if target else {}
        pairs.append({
            "target_id":p.get("target_id"),
            "target_name":scope.get("product","UNKNOWN"),
            "specification":scope.get("specification","UNKNOWN"),
            "region":scope.get("region","UNKNOWN"),
            "customer_group":scope.get("customer_group","UNKNOWN"),
            "supply_pool":scope.get("supply_pool","UNKNOWN"),
            "comparison_state":p.get("comparison",{}).get("state","UNKNOWN"),
            "engine_state":p.get("engine_state","NOT_FORWARDED"),
            "demand_event_sha256":p.get("demand_event"),
            "supply_event_sha256":p.get("supply_event"),
            "unresolved_relief":bool(p.get("unresolved_relief")),
            "forecast_confirmed":False,
            "reason":"BACKFILL_SCREENING_ONLY"
        })
    blocked=Counter(x.get("first_blocker") or x.get("reason") or "UNSPECIFIED"
                    for x in graph["blocked"])
    protected=graph.get("protected_result",{})
    # No actual issuance/validation by a human; no S-stage can be earned here.
    return {"graph_status":"PASS_EXISTING_GRAPH_BACKFILL",
            "source_docs":len(docs),"source_reference_checks":graph["reference_checks"],
            "graph_observations":len(graph["observations"]),
            "graph_edges":len(graph["edges"]),
            "rejected_relation_edges":len(graph["rejected_links"]),
            "complete_target_events":graph["complete_target_events"],
            "independent_demand_supply_pairs":graph["independent_pairs"],
            "comparable_period_pairs":graph["comparable_period_pairs"],
            "potential_gaps":sum(p["comparison_state"] in ("POSSIBLE_TIMING_GAP",
                       "POSSIBLE_QUANTITY_GAP") for p in pairs),
            "backfill_protected_candidates":len(protected.get("candidates",[])),
            "pairs":pairs,"blocked_reasons":dict(blocked),
           "protected_forecast_status":protected.get("forecast_performance",{}).get("status") or "UNVERIFIED"}

def run(frozen, *, fetch_fn=fetch_one, now=None):
    if len(frozen)!=45:
        raise ValueError("NOT_EXACT_VERIFIED45_INPUT")
    locks={host:threading.Lock() for host in {r["source_host"] for r in frozen}}
    statuses=[];docs=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures={pool.submit(fetch_fn,row,locks):row["document_id"] for row in frozen}
        for future in as_completed(futures):
            did=futures[future]
            try:
                status,doc=future.result()
            except Exception as exc:
                status={"document_id":did,"reaccess":"UNHANDLED_EXCEPTION",
                        "first_blocker":"UNHANDLED_"+type(exc).__name__}
                doc=None
            statuses.append(status)
            if doc is not None:docs.append(doc)
    statuses.sort(key=lambda r:r["document_id"])
    docs.sort(key=lambda r:r["document_id"])
    if len(statuses)!=45 or len({r["document_id"] for r in statuses})!=45:
        raise ValueError("INCOMPLETE_45_REACCESS")
    proof=graph_safe_summary(docs,now=now)
    counts=Counter(s.get("reaccess","UNKNOWN") for s in statuses)
    reasons=Counter(s.get("first_blocker","UNKNOWN") for s in statuses)
    issuer=sum(s.get("issuer_primary_verified") is True for s in statuses)
    # Even a historical source-supported gap needs independent researcher
    # validation and future-time pre-public evaluation. No promotions here.
    report={
        "format":"bct-session6-cross-sector-original-source-audit-v1",
        "evaluated_at_utc":utc_now(),"status":"PASS_COMPLETED_READ_ONLY_SOURCE_AUDIT",
        "scope":"45 previously FULL verified S5 originals across every sector",
        "input_s5_run":S5_ARTIFACT_RUN,"input_s5_artifact_id":S5_ARTIFACT_ID,
        "previous_verified_full":45,
        "reaccess_attempted":len(statuses),
        "current_same_hash_verified":len(docs),
        "same_version_reaccess_rate":len(docs)/45,
        "issuer_primary_verified":issuer,
        "source_reaccess_counts":dict(counts),
        "first_blocker_counts":dict(reasons),
        "existing_graph":{k:v for k,v in proof.items() if k!="pairs"},
        "independent_demand_supply_pairs":proof["independent_demand_supply_pairs"],
        "eligible_verified_bottlenecks":0,
        "research_pairs_not_promoted":len(proof["pairs"]),
        "S1_S2_S3_new":0,
        "model_label_precision_recall":"NOT_MEASURED",
        "actual_future_12_36_month_forecast_success":"UNVERIFIED",
        "newly_accepted_newspaper_as_issuer":0,
        "paid_AI_calls":0,
        "source_http_requests_max":45,
        "publisher_access_bypass":0,
        "operating_branch_or_db_writes":0,
        "source_body_redistributed":False,
        "original_sample_unmodified":True
    }
    return report,statuses,proof["pairs"]

def write_csv(path,rows,cols):
    with Path(path).open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader()
        for r in rows:w.writerow({key:safe_csv(r.get(key)) for key in cols})

def main(argv=None):
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--previous",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args(argv)
    frozen=read_frozen(args.previous)
    result,per_doc,pairs=run(frozen)
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    (out/"cross_evidence_summary.json").write_text(
       json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    write_csv(out/"per_article_evidence_status_45.csv",per_doc,
        ["document_id","source_url","source_host","old_body_sha256",
         "current_body_sha256","source_version_same","reaccess",
         "first_blocker","issuer_primary_verified","readable_event_count",
         "demand_events","supply_events","relief_events",
         "scope_complete_events","qualified_supplier_events",
         "explicit_future_need_events","extraction_method","error_type"])
    write_csv(out/"independent_pair_research_queue.csv",pairs,
        ["target_id","target_name","specification","region","customer_group",
         "supply_pool","comparison_state","engine_state","unresolved_relief",
         "demand_event_sha256","supply_event_sha256",
         "forecast_confirmed","reason"])
    report=[
        "# BCT 세션 6 — 서로 독립적인 수요·공급 근거 교차검증",
        "",
        "**45건은 지난 세션에서 출처가 확인된 뉴스 원문입니다. 그것만으로 기업·기관의 공식 1차 자료라고 판단하지 않습니다.**",
        "",
        f"- 시험 대상: 기존 VERIFIED_FULL 45건 전체",
        f"- 동일 본문 해시로 재접근·재검증: **{result['current_same_hash_verified']}건**",
        f"- 발행 주체가 직접 근거를 제공하는 1차 자료로 확인: **{result['issuer_primary_verified']}건**",
        f"- 독립 수요·공급 신호쌍(기존 보수적 graph 판정): **{result['independent_demand_supply_pairs']}건**",
        f"- 공식 S1/S2/S3로 신규 승격: **0건**",
        "",
        "## 이전 원문이 다시 확인되지 않은 사유",
        "| 상태 | 문서 |","|---|---:|"
    ]
    for key,count in sorted(result["source_reaccess_counts"].items()):
        report.append(f"| {key} | {count} |")
    report.extend(["",
        "## 그래프 검증 사유",
        "| 보류 원인 | 건수 |","|---|---:|"])
    for key,count in sorted(result["existing_graph"].get("blocked_reasons",{}).items(),key=lambda kv:-kv[1])[:20]:
        report.append(f"| {key} | {count} |")
    report.extend([
        "",
        "실험은 원문 문맥을 다시 읽은 BACKFILL 연구용입니다. 실제 뉴스 공개 전 예측 성공으로 승격하지 않습니다.",
        "같은 제품 단어·기사 헤드라인·출처가 다른 신문 두 곳만으로는 적격 공급 부족이 입증되지 않습니다.",
        "개별 기사 상태는 CSV, 검증된 그래프의 연결 시도는 별도 CSV에 기록했습니다.",
        "원문 본문, 제3자 기사 발췌, 실증 중 원본 HTML은 아티팩트에 포함하지 않습니다."])
    (out/"session6_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print("BCT_SESSION6_SUMMARY="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
