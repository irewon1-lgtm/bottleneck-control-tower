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
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, body in {
        ".nojekyll": b"", "index.html": html.encode("utf-8"),
        "app.js": js.encode("utf-8"),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "api/dashboard.json": pack(data),
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
