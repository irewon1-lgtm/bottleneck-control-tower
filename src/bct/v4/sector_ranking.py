"""Honest, reproducible sector-record rankings for the public V4 view.

Counts are unique source-linked *research records*, not proven bottlenecks,
independent supply/demand pairs, stocks or model product proposals. Reading an
older public dashboard is optional and never changes any source or state.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import re
from urllib.request import Request, urlopen

PUBLIC_SITE = "https://irewon1-lgtm.github.io/bottleneck-control-tower/"
VALID_KINDS = frozenset({"reviewed", "structured", "discovery"})
UNCLASSIFIED = frozenset({"산업 확인 필요", "산업 추가 확인", "아직 분류하지 않은 산업"})
MAX_DASHBOARD = 6 * 1024 * 1024
MAX_MANIFEST = 32 * 1024


def ranks(records):
    """Competition ranking: 1, 1, 3, ordered by unique saved evidence IDs."""
    if not isinstance(records, list):
        raise ValueError("RANK_RECORDS_INVALID")
    grouped = defaultdict(dict)
    unclassified = 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("RANK_RECORD_INVALID")
        if record.get("category") not in VALID_KINDS:
            continue
        key = record.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("RANK_RECORD_ID_INVALID")
        name = record.get("industry")
        if not isinstance(name, str) or not name.strip() or name in UNCLASSIFIED:
            unclassified += 1
            continue
        name = name.strip()
        if key in grouped[name]:
            raise ValueError("RANK_DUPLICATE_RECORD_IN_SECTOR")
        grouped[name][key] = record
    rows = []
    for name, records_by_id in grouped.items():
        value = list(records_by_id.values())
        types = {type_name: sum(r["category"] == type_name for r in value) for type_name in ("reviewed", "structured", "discovery")}
        published = sorted((r["published_at"] for r in value if isinstance(r.get("published_at"), str)
                            and re.match(r"^\d{4}-\d\d-\d\d", r["published_at"])), reverse=True)
        rows.append({"name": name, "evidence_count": len(value), "reviewed_count": types["reviewed"],
                     "structured_count": types["structured"], "discovery_count": types["discovery"],
                     "recent_publication": published[0] if published else None})
    rows.sort(key=lambda r: (-r["evidence_count"], r["name"]))
    previous_count = None
    for i, item in enumerate(rows, 1):
        if item["evidence_count"] != previous_count:
            rank = i
            previous_count = item["evidence_count"]
        item["rank"] = rank
    return {"rows": rows, "unclassified_count": unclassified,
            "ranked_record_count": sum(r["evidence_count"] for r in rows),
            "count_kind": "SOURCE_LINKED_RESEARCH_RECORDS_NOT_VERIFIED_SHORTAGES",
            "includes_unverified_discovery": True}


def previous_public_snapshot(*, opener=urlopen, timeout=7):
    """Fetch and SHA256-check the *already published* previous site, if online.

    This is an optional comparison source, not an input to research or a Gate.
    The web visitor sees 'previous unavailable' instead of invented rankings if
    the previous snapshot cannot be authenticated or retrieved.
    """
    def get(path, max_bytes):
        req = Request(PUBLIC_SITE + path, headers={"Cache-Control": "no-cache", "User-Agent": "BCT-previous-public-rank-read"})
        with opener(req, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
        if not raw or len(raw) > max_bytes:
            raise ValueError("PREVIOUS_PUBLIC_SIZE")
        return raw
    try:
        manifest = json.loads(get("build-manifest.json", MAX_MANIFEST))
        if (manifest.get("site_type") != "PUBLIC_STATIC_READ_ONLY"
                or manifest.get("source_branch") != "codex/bct-v4-integration"
                or not re.fullmatch(r"[a-f0-9]{40}", str(manifest.get("code_commit", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(manifest.get("dashboard_sha256", "")))):
            raise ValueError("PREVIOUS_PUBLIC_MANIFEST")
        raw = get("api/dashboard.json", MAX_DASHBOARD)
        if hashlib.sha256(raw).hexdigest() != manifest["dashboard_sha256"]:
            raise ValueError("PREVIOUS_PUBLIC_HASH_MISMATCH")
        dashboard = json.loads(raw)
        if dashboard.get("schema") != "bct-v4-dashboard-1":
            raise ValueError("PREVIOUS_PUBLIC_SCHEMA")
        prior = ranks(dashboard.get("records"))
        return {"status": "VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT",
                "generated_at": manifest.get("generated_at"),
                "data_at": manifest.get("data_at"),
                "source_dashboard_sha256": manifest["dashboard_sha256"],
                "ranks": {row["name"]: {"rank": row["rank"], "evidence_count": row["evidence_count"]}
                          for row in prior["rows"]}}
    except (OSError, ValueError, KeyError, TypeError, OverflowError, json.JSONDecodeError):
        return {"status": "PREVIOUS_PUBLIC_SNAPSHOT_UNAVAILABLE",
                "generated_at": None, "data_at": None, "source_dashboard_sha256": None, "ranks": {}}
