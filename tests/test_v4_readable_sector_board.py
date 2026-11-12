"""Sector board: source-grounded counting, tie ranks and authentic prior display.

No live fetch, model or DB mutation is needed to test the ranking policy.
"""
import hashlib
import io
import json
from pathlib import Path

import pytest

from bct.v4.sector_ranking import ranks, previous_public_snapshot


def entry(industry, index, kind="reviewed", when=None):
    return {"id": format(index, "064x"), "category": kind, "industry": industry,
            "published_at": when, "product": "테스트 자료 항목"}


def test_evidence_is_record_count_not_cpu_mentions_or_verified_bottlenecks():
    rows = [entry("전력·발전", i, "structured") for i in range(1, 4)]
    rows += [entry("자동차·배터리", i) for i in range(4, 7)]
    rows += [entry("바이오·의약", 7), entry("산업 확인 필요", 8)]
    rows += [entry("산업 추가 확인", 9, "cpu_product")]
    rows += [entry("전력·발전", 10, "cpu_product")]
    result = ranks(rows)
    assert [(x["rank"], x["evidence_count"]) for x in result["rows"]] == [(1, 3), (1, 3), (3, 1)]
    assert result["ranked_record_count"] == 7
    assert result["unclassified_count"] == 1
    assert not any(x["name"] == "산업 확인 필요" for x in result["rows"])
    assert all(x["rank"] >= 1 for x in result["rows"])
    assert "NOT_VERIFIED_SHORTAGES" in result["count_kind"]


def test_same_id_cannot_be_doubly_counted_within_sector():
    with pytest.raises(ValueError, match="DUPLICATE"):
        ranks([entry("전력·발전", 1), entry("전력·발전", 1)])
    with pytest.raises(ValueError, match="ID_INVALID"):
        ranks([{"id": "bad", "category": "reviewed", "industry": "전력·발전"}])


def test_previous_snapshot_requires_sha256_and_real_public_manifest():
    base = [{"id": format(i, "064x"), "category": "reviewed", "industry": "바이오·의약"}
            for i in range(1, 3)]
    page = {"schema": "bct-v4-dashboard-1", "records": base}
    raw = (json.dumps(page) + "\n").encode()
    manifest = {"site_type": "PUBLIC_STATIC_READ_ONLY", "source_branch": "codex/bct-v4-integration",
                "code_commit": "a" * 40, "dashboard_sha256": hashlib.sha256(raw).hexdigest(),
                "generated_at": "2026-11-11T12:00:00+00:00", "data_at": "2026-11-11T11:00:00+00:00"}
    files = {"build-manifest.json": json.dumps(manifest).encode(), "api/dashboard.json": raw}

    class Response:
        def __init__(self, body): self.body = io.BytesIO(body)
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, length): return self.body.read(length)

    def opener(request, *, timeout):
        path = request.full_url.rsplit("bottleneck-control-tower/", 1)[1]
        return Response(files[path])

    result = previous_public_snapshot(opener=opener)
    assert result["status"] == "VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT"
    assert result["ranks"]["바이오·의약"] == {"rank": 1, "evidence_count": 2}
    assert result["source_dashboard_sha256"] == hashlib.sha256(raw).hexdigest()
    files["api/dashboard.json"] += b"x"
    assert previous_public_snapshot(opener=opener)["status"] == "PREVIOUS_PUBLIC_SNAPSHOT_UNAVAILABLE"


def test_exporter_and_first_image_ui_keep_source_provenance():
    root = Path(__file__).resolve().parents[1]
    exporter = (root / "tools/v4_dashboard_static_export.py").read_text()
    html = (root / "src/bct/v4/dashboard_web/index.html").read_text()
    js = (root / "src/bct/v4/dashboard_web/app.js").read_text()
    css = (root / "src/bct/v4/dashboard_web/style.css").read_text()
    assert 'data["sector_rankings"] = ranks(data["records"])' in exporter
    assert 'previous_public_snapshot() if os.environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages"' in exporter
    assert 'data-nav="overview"' in html
    assert "function firstOverview()" in js
    assert "function boardPrevious(" in js
    assert 'data.sector_rank_previous' in js
    assert '"최근 예약 실패"' in js  # Never call a manual run a scheduled success.
    assert '"원문 보기"' in js and 'openDetail(r.id)' in js
    assert "bct-rank-columns" in css and "bct-process-grid" in css
    assert "전력 설비 (18건)" not in html
    assert "반도체 생산 장비" not in js  # No sample values in production.


def test_mobile_rank_table_stacks_all_seven_source_columns():
    root = Path(__file__).resolve().parents[1]
    css = (root / "src/bct/v4/dashboard_web/style.css").read_text()
    assert "Mobile: preserve the approved desktop table" in css
    for expected in (
        "grid-template-areas:",
        '"sector sector sector sector"',
        '"current previous change count"',
        '"recent recent action action"',
        "tbody td:nth-child(1){grid-area:current}",
        "tbody td:nth-child(2){grid-area:previous}",
        "tbody td:nth-child(3){grid-area:change}",
        "tbody td:nth-child(4){grid-area:sector",
        "tbody td:nth-child(5){grid-area:count}",
        "tbody td:nth-child(6){grid-area:recent",
        "tbody td:nth-child(7){grid-area:action",
        "content:attr(data-label)",
        "width:100%;min-width:0",
    ):
        assert expected in css
