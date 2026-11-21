#!/usr/bin/env python3
"""Cost-zero RSS first-pass triage, with verified legacy sidecar context.

All 10k+ RSS records are visited exactly once. This reads only RSS title/snippet.
Historical body screening is referenced but never represented as newly read.
No API, publication, evidence promotion, or writes to any source database.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from urllib.parse import urlsplit

from bct.future_bottleneck import screen
from bct.radar_signals import extract
from bct.future_github import assemble

KINDS = ("DEMAND", "SUPPLY", "RELIEF")
BODY_STATUSES = {"FULL", "PARTIAL", "UNAVAILABLE", "NOT_IN_SIDECAR", "UNKNOWN"}
EXPECTED_SIDECAR_FORMAT = "bct-sharded-sidecar-v1"


def git_bytes(ref, name):
    process = subprocess.run(["git", "show", ref + ":" + name], capture_output=True)
    if process.returncode:
        raise ValueError("Pinned Git source missing: " + name)
    return process.stdout


def safe_cell(value):
    data = "" if value is None else str(value)
    if data.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + data
    return data


def paths_for(row):
    # Explicit separation: RSS title and summary only, never original body.
    metadata = (row["title"] or "") + "\n" + (row["snippet"] or "")
    broad = screen(metadata)
    narrow = extract(row["title"] or "", row["snippet"])
    paths = tuple(k for k in KINDS if k in broad["discovery_paths"])
    narrow_signals = sorted(set(s["signal"] for s in narrow))
    return paths, narrow_signals, broad


def triage_one(row, sidecar=None):
    paths, narrow, broad = paths_for(row)
    body_status = (sidecar or {}).get("body_status", "NOT_IN_SIDECAR")
    if body_status not in BODY_STATUSES:
        body_status = "UNKNOWN"
    # This is only a QUEUE priority to acquire/review *sources*, not a bottleneck score.
    if len(paths) >= 2 and narrow:
        priority = "P1_MULTISIGNAL_METADATA"
    elif narrow or len(paths) >= 2:
        priority = "P2_TEXT_CUE"
    elif paths:
        priority = "P3_BROAD_TEXT_CUE"
    else:
        priority = "P4_NO_METADATA_CUE"
    prior_decision = (sidecar or {}).get("decision", "NOT_IN_SIDECAR")
    prior_candidate = bool((sidecar or {}).get("candidate"))
    # A title-only non-match cannot erase an older FULL-body screening lead.
    # Even those older FULL-body leads remain UNVERIFIED until independent review.
    if body_status == "FULL" and prior_candidate and prior_decision in ("CONTEXT_REVIEW", "CANDIDATE_ONLY"):
        lane = "Q1_PRIOR_FULL_BODY_LEAD"
    elif body_status == "PARTIAL" and prior_candidate:
        lane = "Q2_PRIOR_PARTIAL_BODY_LEAD"
    elif body_status == "UNAVAILABLE" and prior_candidate:
        lane = "Q3_PRIOR_UNAVAILABLE_LEAD_HOLD"
    elif priority != "P4_NO_METADATA_CUE":
        lane = "Q4_METADATA_SIGNAL_NEEDS_SOURCE"
    else:
        lane = "Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING"
    return {
        "id": row["id"], "source": row["source"], "url": row["url"],
        "title": row["title"], "published_at": row["published_at"],
        "collected_at": row["collected_at"], "metadata_classification": "TITLE_SNIPPET_ONLY",
        "headline_snippet_available": bool(row["title"] or row["snippet"]),
        "title_snippet_signal_paths": list(paths), "narrow_signal_codes": narrow,
        "metadata_conditional": bool(broad["context_review"]),
        "metadata_priority": priority,
        "combined_review_lane": lane,
        "previous_body_status": body_status,
        "prior_body_screened": bool(sidecar and body_status in ("FULL", "PARTIAL")),
        "previous_body_screening_decision": (sidecar or {}).get("decision", "NOT_IN_SIDECAR"),
        "previous_body_candidate_unverified": bool((sidecar or {}).get("candidate")),
        "prior_review_required": True,
        "final_bottleneck_verified": False,
        "stage": "NOT_EVALUATED",
    }


def evaluate(rows, sidecar_results):
    rows = list(rows)
    by_id = {r["id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("RSS_ID_NOT_UNIQUE")
    orphan = set(sidecar_results) - set(by_id)
    if orphan:
        raise ValueError("SIDECAR_HAS_NONCANONICAL_IDS: " + str(len(orphan)))
    source_counts = Counter()
    narrow_counts = Counter()
    path_counts = Counter()
    path_combo_counts = Counter()
    priorities = Counter()
    combined_lanes = Counter()
    rescued_p4_from_full_body = 0
    body_counts = Counter()
    coverage = Counter()
    caveats = Counter()
    out = []
    for row in rows:
        if not row["id"] or not row["title"] or not row["url"]:
            raise ValueError("RSS_ARTICLE_REQUIRED_FIELDS_MISSING")
        value = triage_one(row, sidecar_results.get(row["id"]))
        out.append(value)
        source_counts[value["source"]] += 1
        priorities[value["metadata_priority"]] += 1
        combined_lanes[value["combined_review_lane"]] += 1
        if value["metadata_priority"] == "P4_NO_METADATA_CUE" and value["combined_review_lane"] == "Q1_PRIOR_FULL_BODY_LEAD":
            rescued_p4_from_full_body += 1
        body_counts[value["previous_body_status"]] += 1
        coverage["with_prior_sidecar" if row["id"] in sidecar_results else "without_prior_sidecar"] += 1
        for k in value["title_snippet_signal_paths"]:
            path_counts[k] += 1
        for k in value["narrow_signal_codes"]:
            narrow_counts[k] += 1
        path_combo_counts["+".join(value["title_snippet_signal_paths"]) or "NONE"] += 1
        if value["metadata_conditional"]:
            caveats["conditional_or_plan_language"] += 1
        if not row["snippet"]:
            caveats["rss_summary_missing"] += 1
        if not row["published_at"]:
            caveats["rss_publication_date_missing"] += 1
    if (sum(body_counts.values()) != len(rows) or sum(priorities.values()) != len(rows)
            or sum(combined_lanes.values()) != len(rows)):
        raise ValueError("INCOMPLETE_FIRSTPASS_COUNTS")
    return out, {
        "total": len(rows), "screened_title_snippet": len(out),
        "prior_sidecar_linked": coverage["with_prior_sidecar"],
        "no_prior_sidecar": coverage["without_prior_sidecar"],
        "metadata_priorities": dict(sorted(priorities.items())),
        "combined_review_lanes": dict(sorted(combined_lanes.items())),
        "rescued_p4_using_prior_full_body_leads": rescued_p4_from_full_body,
        "previous_body_status": dict(sorted(body_counts.items())),
        "title_snippet_signal_article_counts": dict(sorted(path_counts.items())),
        "headline_snippet_signal_combinations": dict(sorted(path_combo_counts.items())),
        "narrow_signal_counts": dict(sorted(narrow_counts.items())),
        "missing_or_caution": dict(sorted(caveats.items())),
        "source_count": len(source_counts),
        "top_sources": [{"source":source,"count":count} for source,count in source_counts.most_common(15)],
        "true_positive_or_predictive_accuracy": "NOT_MEASURED",
        "independent_supply_demand_verified": "NOT_MEASURED",
        "data_scope": "RSS_TITLE_SNIPPET_TRIAGE_WITH_PRIOR_BODY_STATUS",
        "source_document_bodies_newly_read": 0,
        "candidate_promotion": 0,
        "paywall_bypassed": 0,
        "api_requests": 0,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--data-sha",required=True)
    parser.add_argument("--sidecar-sha",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    state=json.loads(git_bytes(args.data_sha,"state.json"))
    raw=git_bytes(args.data_sha,"canonical.sqlite3")
    if hashlib.sha256(raw).hexdigest()!=state["sha256"]:
        raise ValueError("RSS_CANONICAL_SHA_MISMATCH")
    temp=output/"_canonical.sqlite3"
    temp.write_bytes(raw)
    try:
        with sqlite3.connect("file:"+str(temp.resolve())+"?mode=ro&immutable=1",uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("RSS_INTEGRITY_FAILURE")
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute(
                "SELECT id,source,title,url,snippet,published_at,collected_at "
                "FROM radar_items WHERE status='active' ORDER BY collected_at,id")]
            total=db.execute("SELECT count(*) FROM radar_items").fetchone()[0]
            if total!=state["radar_items"] or len(rows)!=total:
                raise ValueError("RSS_RECORD_COUNT_DIVERGENCE")
        manifest=json.loads(git_bytes(args.sidecar_sha,"future-candidates.json"))
        if manifest.get("format")!=EXPECTED_SIDECAR_FORMAT:
            raise ValueError("PRIOR_SIDECAR_FORMAT_UNEXPECTED")
        verified_parts=0
        def shard(part):
            nonlocal verified_parts
            raw=git_bytes(args.sidecar_sha,part["path"])
            verified_parts+=1
            return raw
        prior=assemble(manifest,shard)
        sidecar=prior.get("results",{})
        if not isinstance(sidecar,dict):
            raise ValueError("PRIOR_SIDECAR_RESULTS_MISSING")
        results,summary=evaluate(rows,sidecar)
        if len(results)!=state["radar_items"]:
            raise ValueError("FIRSTPASS_INCOMPLETE")
        summary.update({
            "status":"PASS_READ_ONLY_METADATA_FIRSTPASS",
            "rss_git_sha":args.data_sha, "rss_sqlite_sha256":state["sha256"],
            "rss_run_id":state["run_id"],
            "sidecar_git_sha":args.sidecar_sha,
            "sidecar_shards_sha256_verified":verified_parts,
            "legacy_sidecar_record_count":len(sidecar),
            "unprocessed_original_body":sum(
                r["previous_body_status"]!="FULL" for r in results),
            "next_action":"FULL_BODY_CAPTURE_AND_SOURCE_PROVENANCE_REVIEW",
        })
        priority_sort={"P1_MULTISIGNAL_METADATA":0,"P2_TEXT_CUE":1,
                       "P3_BROAD_TEXT_CUE":2,"P4_NO_METADATA_CUE":3}
        combined_sort={"Q1_PRIOR_FULL_BODY_LEAD":0,"Q2_PRIOR_PARTIAL_BODY_LEAD":1,
                       "Q3_PRIOR_UNAVAILABLE_LEAD_HOLD":2,
                       "Q4_METADATA_SIGNAL_NEEDS_SOURCE":3,
                       "Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING":4}
        ordered=sorted(results,key=lambda r:(combined_sort[r["combined_review_lane"]],
                   priority_sort[r["metadata_priority"]], r["collected_at"],r["id"]))
        columns=["id","source","url","title","published_at","collected_at",
                 "metadata_classification","metadata_priority","combined_review_lane","title_snippet_signal_paths",
                 "narrow_signal_codes","metadata_conditional","previous_body_status",
                 "prior_body_screened","previous_body_screening_decision",
                 "previous_body_candidate_unverified","stage"]
        with (output/"article_firstpass.csv").open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(columns)
            for r in ordered:
                w.writerow([safe_cell("|".join(r[x]) if isinstance(r[x],list) else r[x]) for x in columns])
        (output/"firstpass_summary.json").write_text(
            json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        rows_md=["# BCT 세션 3 — 전체 RSS 1차 메타데이터 분석",
                 "",
                 "**기사 제목·RSS 요약만 전수 점검했습니다. 원문 10,510건 분석 완료가 아닙니다.**",
                 "",
                 f"- 자료: {summary['total']:,}건, 메타데이터 점검: {summary['screened_title_snippet']:,}건 (100%)",
                 f"- 과거 원문 분석 이력 연결: {summary['prior_sidecar_linked']:,}건",
                 f"- 이력 없음: {summary['no_prior_sidecar']:,}건",
                 f"- 이전 FULL 본문: {summary['previous_body_status'].get('FULL',0):,}건",
                 "- 신규 원문 확보·유료 API·공급 부족 확정: 0건",
                 "",
                 "## 메타데이터 검토 우선순위 — 실제 병목 순위가 아님",
                 "",
                 "| 상태 | 기사 수 |",
                 "|---|---:|"]
        for k in ("P1_MULTISIGNAL_METADATA","P2_TEXT_CUE","P3_BROAD_TEXT_CUE","P4_NO_METADATA_CUE"):
            rows_md.append(f"| {k} | {summary['metadata_priorities'].get(k,0):,} |")
        rows_md += ["","## 기존 본문 신호까지 합친 검토 대기열 — 병목 확정 아님",
                    "| 통합 검토 대기열 | 건수 |","|---|---:|"]
        for k in combined_sort:
            rows_md.append(f"| {k} | {summary['combined_review_lanes'].get(k,0):,} |")
        rows_md.append(f"| 제목 P4지만 과거 FULL 본문에 검토 신호 있음 | {summary['rescued_p4_using_prior_full_body_leads']:,} |")
        rows_md += ["","## 분류된 기사 신호 — 독립 근거로 확정되지 않음",
                    "| 신호 | 기초 일치 기사 수 |","|---|---:|"]
        for k in KINDS:
            rows_md.append(f"| {k} | {summary['title_snippet_signal_article_counts'].get(k,0):,} |")
        rows_md += ["","세션 4에서 평가 표본을 고정해 오탐/누락을 검증해야 합니다.",
                    "sidecar 원문 기록을 재사용했으며 본문은 새로 읽지 않았습니다.",
                    "기사별 표: article_firstpass.csv / 교차 검증 요약: firstpass_summary.json"]
        (output/"firstpass_report.md").write_text("\n".join(rows_md)+"\n",encoding="utf-8")
        print("BCT_SESSION3_FIRSTPASS="+json.dumps(summary,ensure_ascii=False,sort_keys=True))
    finally:
        temp.unlink(missing_ok=True)


if __name__=="__main__":
    main()
