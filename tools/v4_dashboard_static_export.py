"""Export the BCT V4 dashboard to a public, lightweight GitHub Pages site.

Only existing validated dashboard view data and complete evidence details are
exported. No AI, databases, server, credentials, passwords or Netlify runtime.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from bct.v4.dashboard import ASSETS, ResearchReader
from bct.v4.public_research import validate_snapshot, digest
from bct.v4.public_data import validate_acquisition, validate_health, validate_cursor
from v4_public_news_export import build_from_public_branch
from v4_source_intake_public import from_data_snapshot
from v4_future_sidecar_index import retrieve as future_screening_index
from v4_rss_evidence_registry import from_remote as register_rss_evidence


def pack(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def change_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Dashboard frontend changed; static site conversion requires review: " + old)
    return text.replace(old, new)


def export(repo, dest, commit, *, public_input=None):
    repo, dest = Path(repo).resolve(), Path(dest).resolve()
    if dest != repo / "var/v4/pages-site":
        raise ValueError("Only the generated var/v4/pages-site directory can be replaced")
    operating = collection = workflow = transport = None
    if public_input is not None:
        inputs = Path(public_input)
        for filename, validator in [('research.json', validate_snapshot), ('collection.json', validate_acquisition),
                                    ('workflow.json', validate_health), ('transport.json', validate_cursor)]:
            path = inputs / filename
            if not path.exists():
                continue
            if path.stat().st_size > 192 * 1024:
                raise ValueError('PUBLIC_INPUT_SIZE')
            value = validator(json.loads(path.read_text()))
            if filename == 'research.json': operating = value
            elif filename == 'collection.json': collection = value
            elif filename == 'workflow.json': workflow = value
            else: transport = value
    reader = ResearchReader(repo)
    data = reader.dashboard()
    cpu = data.get("research_updates", {}).get("cpu_recovery", {})
    rows = list(data["records"]) + list(cpu.get("records", []))
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)) or any(not re.fullmatch("[a-f0-9]{64}", i) for i in ids):
        raise ValueError("Duplicate or malformed evidence IDs")
    if len(data["records"]) != data["counts"]["evidence"]:
        raise ValueError("Unmatched dashboard evidence count")
    summary = cpu.get("summary", {})
    expected_cpu = summary.get("CPU_product_proposals_retained", 0) + summary.get("new_source_reported_actual_event_reviews", 0)
    if len(cpu.get("records", [])) != expected_cpu:
        raise ValueError("Unmatched CPU/reported evidence count")
    at = datetime.now(timezone.utc).isoformat()
    # Source-linked rank counts: not unique shortages or CPU product proposals.
    # The previous rank comes from the independently SHA256-verified last
    # published Pages snapshot, never from invented or local-browser values.
    from bct.v4.sector_ranking import ranks, previous_public_snapshot
    data["sector_rankings"] = ranks(data["records"])
    data["sector_rank_previous"] = (
        previous_public_snapshot() if os.environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages"
        else {"status": "PREVIOUS_PUBLIC_NOT_QUERIED_OUTSIDE_PAGES",
              "generated_at": None, "data_at": None,
              "source_dashboard_sha256": None, "ranks": {}})
    data['historical_data_at'] = data.get('data_at')
    if operating is not None:
        data['operating_research'] = operating
        if operating['clocks']['data_at'] is not None:
            data['data_at'] = operating['clocks']['data_at']
    if collection is not None: data['collection_observation'] = collection
    if workflow is not None: data['workflow_observation'] = workflow
    if transport is not None: data['public_transport'] = transport
    data["source"].update({"read_only": True, "snapshot": True, "mode": "공개 정적 연구 스냅샷"})
    data["code_commit"] = commit
    data["snapshot_generated_at"] = at
    data["publication"] = {"source_branch": "codex/bct-v4-integration",
                           "code_commit": commit, "last_sync_at": at,
                           "status": "PUBLISHED_STATIC_SNAPSHOT",
                           "status_label": "무료 GitHub Pages · 자동 배포",
                           "automatic_deployment": "GITHUB_PAGES_ACTIONS"}
    # Include the entire existing public progress receipt, not just older dashboard records.
    progress = json.loads((repo / "docs/v4/PROGRESS.json").read_text(encoding="utf-8"))
    q = progress.get("quantitative_plan", {})
    data["quantitative_progress"] = {
        "updated_at": q.get("updated_at"), "current_step": q.get("current_step"),
        "status": q.get("status"), "numeric_observations": q.get("numeric_observations", 0),
        "physical_quantity_observations": q.get("physical_quantity_observations", 0),
        "versioned_records": q.get("versioned_records", 0),
        "source_status": {name: {"status": item.get("status"), "counts": item.get("counts", {})}
                          for name, item in q.get("source_status", {}).items()},
    }

    # The RSS source is a separate existing PUBLIC writer. It must not change
    # source-linked candidate rankings or become a verified bottleneck signal.
    rss_news = (build_from_public_branch(repo)
                if os.environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages" else None)
    # The existing pinned Pages consumer accepts automatic acquisition only.
    # The newest successful manual intake remains source bound and is displayed
    # as a SEPARATE verified run, without rebranding the earlier receipt.
    source_capture = (from_data_snapshot(repo, rss_news["data_ref"], rss_news["source_run_id"])
                      if rss_news is not None else None)
    data["latest_source_capture"] = source_capture or {"status": "NOT_VERIFIED_OFFLINE"}
    if rss_news is not None:
        data["rss_news_summary"] = {
            key: val for key, val in rss_news.items()
            if key not in ("articles", "failed_feeds")
        }
        data["rss_news_summary"]["newest_articles"] = rss_news["articles"][:8]
        data["rss_news_summary"]["feed_failure_samples"] = rss_news["failed_feeds"][:11]
    else:
        data["rss_news_summary"] = {
            "format": "bct-public-rss-news-1", "status": "NOT_LOADED_OFFLINE",
            "visible_article_count": None, "new_article_count": None,
            "feed_failed": None, "collected_completed_at": None,
            "newest_articles": [], "feed_failure_samples": []
        }

    # Keep the verified 2026-11-13 full-corpus queue audit explicitly
    # timestamp-bound; the live Future sidecar may already have advanced.
    audit = json.loads((repo / "docs/v4/live-screening-audit-20261113.json").read_text(encoding="utf-8"))
    body_counts = audit.get("body_counts", {})
    if (audit.get("format") != "bct-pinned-full-rss-queue-audit-v1"
            or audit.get("status") != "PASS_READ_ONLY_QUEUE_RECONCILIATION"
            or audit.get("classification") != "PINNED_AUDIT_NOT_CURRENT_PROCESSING_RECEIPT_NOT_VERIFIED_SHORTAGE"
            or set(body_counts) != {"FULL", "PARTIAL", "UNAVAILABLE", "NOT_IN_SIDECAR"}
            or any(type(n) is not int or n < 0 for n in body_counts.values())
            or sum(body_counts.values()) != audit.get("rss_articles")
            or audit["sidecar_results"] + audit["unlinked"] != audit["rss_articles"]
            or audit["selected_future_work"]["completed_in_this_audit"] != 0
            or audit["selected_future_work"]["recent"] + audit["selected_future_work"]["older"]
               != audit["selected_future_work"]["total"]
            or audit["verified_read_only_shards"] != 32
            or not all(re.fullmatch("[0-9a-f]{40}", audit[k]) for k in ("data_commit", "sidecar_commit"))):
        raise ValueError("BCT_PINNED_RSS_AUDIT_UNVERIFIED")
    screening = (future_screening_index(repo)
                 if os.environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages" else None)
    data["source_backlog"] = {
        "format": "bct-source-and-screening-funnel-1",
        "status": "VERIFIED_LIVE_INDEX_AND_PINNED_AUDIT" if screening else "OFFLINE_PINNED_AUDIT_ONLY",
        "classification": "NOT_VERIFIED_BOTTLENECK_EVIDENCE",
        "live_sidecar": screening or {"status":"NOT_QUERIED_OUTSIDE_PAGES"},
        "pinned_audit": audit,
        "audit_matches_live_sidecar": screening["sidecar_commit"] == audit["sidecar_commit"] if screening else None,
        "audit_rss_count_matches_live": (rss_news["visible_article_count"] == audit["rss_articles"]
                                         if rss_news else None),
        "historical_rank_input_count": len(data["records"]),
        "rank_input_not_increased_by_rss": True
    }
    # A real observation only enters the V4 sector research count after exact
    # immutable-sidecar and publisher/body/publication verification. Historic
    # 511 records are retained; rejected or source-group-only leads are NOT
    # silently enrolled as independent supply gaps.
    live_evidence = (register_rss_evidence(repo)
                     if os.environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages"
                     else {"format":"bct-rss-sector-evidence-register-1",
                           "status":"OFFLINE_NOT_QUERIED","screened_articles":0,
                           "source_records":[],"groups":{},"preview":{},
                           "counts":{},"source_verified_sector_count":0})
    data["rss_research_evidence"] = live_evidence
    legacy = {r["name"]:dict(r) for r in data["sector_rankings"]["rows"]}
    for sector,n in ((r["industry"],r) for r in live_evidence["source_records"]):
        if sector not in legacy:
            legacy[sector] = {"name":sector,"evidence_count":0,
                "reviewed_count":0,"structured_count":0,"discovery_count":0,
                "recent_publication":None}
        row=legacy[sector]
        row["evidence_count"]+=1
        row["rss_verified_count"]=row.get("rss_verified_count",0)+1
        if n["published_at"] and n["published_at"] > str(row["recent_publication"] or ""):
            row["recent_publication"]=n["published_at"]
    for row in legacy.values():
        row.setdefault("rss_verified_count",0)
        row["rss_source_lead_count"]=live_evidence.get("groups",{}).get(row["name"],{}).get("source_located_leads",0)
    # Source-group routing hints are not accepted as evidence; they remain
    # useful transparency metrics for why many FULL articles are still pending.
    ordered=sorted(legacy.values(),key=lambda row:(-row["evidence_count"],row["name"]))
    prev=None
    for i,row in enumerate(ordered,1):
        if row["evidence_count"]!=prev:
            rank=i
            prev=row["evidence_count"]
        row["rank"]=rank
    data["sector_rankings_live"]={
        "format":"bct-sector-live-source-bound-1",
        "count_kind":"HISTORICAL_RESEARCH_PLUS_ORIGINAL_VERIFIED_UNPAIRED_OBSERVATIONS",
        "rows":ordered,
        "ranked_record_count":sum(x["evidence_count"] for x in ordered),
        "new_original_verified":len(live_evidence["source_records"]),
        "historical_source_rows":data["sector_rankings"]["ranked_record_count"],
        "includes_unverified_discovery":True,
        "no_verified_supply_shortage_promoted":True,
        "source_sidecar_commit":live_evidence.get("sidecar_commit")
    }
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    html = change_once(html, 'href="/style.css"', 'href="./style.css"')
    html = change_once(html, 'src="/app.js"', 'src="./app.js"')
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    js = change_once(js, 'request("/api/dashboard")', 'request("./api/dashboard.json")')
    js = change_once(js, '"/api/export","button"', '"./api/dashboard.json","button"')
    tick = chr(96)
    var = "$" + "{id}"
    js = change_once(js, "request(" + tick + "/api/evidence/" + var + tick + ")",
                     "request(" + tick + "./api/evidence/" + var + ".json" + tick + ")")
    progress_panel = """
    if (data.quantitative_progress) {
      const q = data.quantitative_progress;
      const p = panel("최신 Q1·Q2·Q3 연구 진행", "공식 통계 수치와 미래 병목 판정은 구분합니다.");
      p.append(add(el("div",null,"stats-grid"),
        stat("수치 관측",q.numeric_observations,"공식 자료 원문에 저장된 관측","▤"),
        stat("실물량 관측",q.physical_quantity_observations,"관측 수이며 적격 공급 확정은 아님","◫"),
        stat("미래 병목 후보",Object.values(data.counts.future_candidates).reduce((a,b)=>a+b,0),"독립 공급 공백 Q3 미검증","◎")));
      p.append(el("p","현재 판정: "+q.status+" · 기록 시각 "+date(q.updated_at),"section-note"),
               link("전체 연구 진행 기록 열기 →","./api/progress.json"));
      content.append(p);
    }
"""
    js = change_once(js, "    recoverySummary();", "    recoverySummary();\n" + progress_panel)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, body in {
        ".nojekyll": b"", "index.html": html.encode("utf-8"),
        "app.js": js.encode("utf-8"),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "api/dashboard.json": pack(data),
        "api/progress.json": pack(progress),
    }.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    if rss_news is not None:
        (dest / "api/rss-news.json").write_bytes(pack(rss_news))
        (dest / "api/source-intake.json").write_bytes(pack(source_capture))
    for name, value in [('research', operating), ('collection', collection), ('workflow', workflow), ('transport', transport)]:
        if value is not None:
            (dest / 'api' / (name + '.json')).write_bytes(pack(value))
    total_size = 0
    for identifier in ids:
        record = reader.evidence(identifier)
        if record.get("id") != identifier or record.get("all_references_verified") is not True:
            raise ValueError("Source reference verification failed: " + identifier)
        body = pack(record)
        target = dest / "api/evidence" / (identifier + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        total_size += len(body)
    manifest = {
        "source_branch": "codex/bct-v4-integration", "code_commit": commit,
        "generated_at": at, "data_at": data.get("data_at"),
        "dashboard_sha256": hashlib.sha256((dest / "api/dashboard.json").read_bytes()).hexdigest(),
        "evidence_count": len(ids), "evidence_bytes": total_size,
        "site_type": "PUBLIC_STATIC_READ_ONLY", "new_ai_calls": 0
    }

    manifest["rss_research_sha256"] = hashlib.sha256(pack(live_evidence)).hexdigest()
    manifest["rss_research_sidecar_commit"] = live_evidence.get("sidecar_commit")
    manifest["rss_research_verified_source_records"] = len(live_evidence["source_records"])
    manifest["screening_sidecar_commit"] = screening["sidecar_commit"] if screening else None
    manifest["screening_funnel_sha256"] = hashlib.sha256(pack(data["source_backlog"])).hexdigest()
    manifest["source_intake_sha256"] = (
        hashlib.sha256((dest / "api/source-intake.json").read_bytes()).hexdigest()
        if source_capture is not None else None
    )
    manifest["source_intake_run_id"] = (
        source_capture["source_run_id"] if source_capture is not None else None
    )
    manifest["rss_news_sha256"] = (
        hashlib.sha256((dest / "api/rss-news.json").read_bytes()).hexdigest()
        if rss_news is not None else None
    )
    manifest["rss_source_run_id"] = rss_news["source_run_id"] if rss_news else None
    manifest["rss_article_count"] = rss_news["visible_article_count"] if rss_news else None
    manifest["rss_data_ref"] = rss_news["data_ref"] if rss_news else None
    manifest['historical_data_at'] = data['historical_data_at']
    manifest['research_generation'] = operating['generation'] if operating else None
    manifest['research_snapshot_sha256'] = operating['snapshot_sha256'] if operating else None
    manifest['transport_cursor_sha256'] = digest(transport) if transport else None
    manifest['collection_generation'] = ({key: collection[key] for key in
        ('collection_started_at', 'RSS_run_id', 'run_id', 'run_attempt', 'completed_at')} if collection else None)
    (dest / "build-manifest.json").write_bytes(pack(manifest))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--output", type=Path, default=Path("var/v4/pages-site"))
    p.add_argument("--commit", default=os.environ.get("BCT_CODE_SHA", "LOCAL_NOT_DEPLOYED"))
    p.add_argument('--public-input', type=Path)
    a = p.parse_args()
    export(a.repo, a.output if a.output.is_absolute() else a.repo / a.output, a.commit, public_input=a.public_input)
