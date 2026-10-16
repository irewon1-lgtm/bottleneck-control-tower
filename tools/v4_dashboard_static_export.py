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


def pack(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def change_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Dashboard frontend changed; static site conversion requires review: " + old)
    return text.replace(old, new)


def export(repo, dest, commit):
    repo, dest = Path(repo).resolve(), Path(dest).resolve()
    if dest != repo / "var/v4/pages-site":
        raise ValueError("Only the generated var/v4/pages-site directory can be replaced")
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
    (dest / "build-manifest.json").write_bytes(pack(manifest))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--output", type=Path, default=Path("var/v4/pages-site"))
    p.add_argument("--commit", default=os.environ.get("BCT_CODE_SHA", "LOCAL_NOT_DEPLOYED"))
    a = p.parse_args()
    export(a.repo, a.output if a.output.is_absolute() else a.repo / a.output, a.commit)
