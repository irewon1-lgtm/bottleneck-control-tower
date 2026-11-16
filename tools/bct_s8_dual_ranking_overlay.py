"""Two clearly separated, source-bound BCT Pages rankings.

This is a *read-only presentation overlay*. The existing V4 core, original
sector judgments, LIVE ledger, legacy 511 records, and model are unchanged.
Basic-screening ranks are only research priorities, never verified shortages.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

REPO = "irewon1-lgtm/bottleneck-control-tower"
SIDE_BRANCH = "future-bottleneck-data"
FORMAT = "bct-s8-dual-readonly-rankings-v1"
LIMIT = 200
HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
S7_ANCHOR = '<a href="./source-truth/" class="bct-s7-link" aria-label="원출처 근거 검증 현황 보기">근거 검증 현황</a>'
BASIC_ANCHOR = '<a href="./rankings/#signals" class="bct-ranking-link" aria-label="기본분석 선행신호 순위 보기">기본분석 순위</a>'
EVIDENCE_ANCHOR = '<a href="./rankings/#evidence" class="bct-ranking-link" aria-label="원출처 근거 순위 보기">근거 검증 순위</a>'
MAX_GZIP = 32 * 1024 * 1024
MAX_JSON = 240 * 1024 * 1024


def require(test, reason):
    if not test:
        raise ValueError("BCT_DUAL_RANK_" + reason)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def git_sha1(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def api_json(url):
    require(bool(re.fullmatch(r"repos/irewon1-lgtm/bottleneck-control-tower/[A-Za-z0-9/_?=.&-]+", url)),
            "UNEXPECTED_GITHUB_ENDPOINT")
    proc = subprocess.run(["gh", "api", url], capture_output=True, check=True, timeout=150)
    return json.loads(proc.stdout)


def branch_sha(branch):
    require(branch in (SIDE_BRANCH, "data"), "INVALID_BRANCH")
    value = api_json("repos/" + REPO + "/git/ref/heads/" + branch)
    commit = value.get("object", {}).get("sha")
    require(isinstance(commit, str) and HEX40.fullmatch(commit), "BRANCH_SHA")
    return commit


def read_blob(git_sha):
    require(isinstance(git_sha, str) and HEX40.fullmatch(git_sha), "BLOB_SHA_FORMAT")
    blob = api_json("repos/" + REPO + "/git/blobs/" + git_sha)
    require(blob.get("encoding") == "base64" and blob.get("sha") == git_sha,
            "BLOB_RESPONSE_IDENTITY")
    raw = base64.b64decode(blob["content"], validate=False)
    require(len(raw) <= MAX_JSON and git_sha1(raw) == git_sha, "BLOB_IDENTITY_CHECK")
    return raw


def read_named(commit, name):
    require(name in ("future-candidates.json", "future-candidates.ui.json.gz",
                     "state.json"), "FILENAME_NOT_APPROVED")
    value = api_json("repos/" + REPO + "/contents/" + name + "?ref=" + commit)
    blob_sha = value.get("sha")
    require(isinstance(blob_sha, str) and HEX40.fullmatch(blob_sha), "FILE_SHA")
    return read_blob(blob_sha), blob_sha


def acquire_sidecar():
    """An actual SHA-verified display projection of the analyzed article corpus."""
    commit = branch_sha(SIDE_BRANCH)
    manifest_raw, _ = read_named(commit, "future-candidates.json")
    manifest = json.loads(manifest_raw)
    counts = manifest.get("item_counts", {})
    require(manifest.get("format") == "bct-sharded-sidecar-v1"
            and isinstance(counts, dict)
            and type(counts.get("results")) is int and counts["results"] > 0
            and type(counts.get("hypotheses")) is int
            and HEX64.fullmatch(str(manifest.get("document_sha256", ""))),
            "SIDECAR_MANIFEST")
    compressed, blob_sha = read_named(commit, "future-candidates.ui.json.gz")
    require(0 < len(compressed) <= MAX_GZIP, "UI_COMPRESSED_BOUNDS")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as reader:
        unpacked = reader.read(MAX_JSON + 1)
    require(0 < len(unpacked) <= MAX_JSON, "UI_DECOMPRESSED_BOUNDS")
    envelope = json.loads(unpacked)
    require(envelope.get("format") == "bct-sidecar-display-v1"
            and envelope.get("source_document_sha256") == manifest["document_sha256"]
            and isinstance(envelope.get("payload"), str)
            and sha256(envelope["payload"].encode("utf-8")) == envelope.get("payload_sha256"),
            "DISPLAY_BLOB_MANIFEST_OR_SHA_MISMATCH")
    source = json.loads(envelope["payload"])
    require(type(source.get("results")) is dict
            and type(source.get("hypotheses")) is dict
            and len(source["results"]) == counts["results"]
            and len(source["hypotheses"]) == counts["hypotheses"],
            "DISPLAY_RECORD_COUNTS_NOT_MANIFEST")
    require(branch_sha(SIDE_BRANCH) == commit, "SIDECAR_REF_MOVED_DURING_READ")
    return source, {
        "sidecar_commit": commit,
        "source_document_sha256": manifest["document_sha256"],
        "sidecar_ui_blob_sha1": blob_sha,
        "sidecar_ui_sha256": sha256(compressed),
        "articles_with_screening_result": len(source["results"]),
        "hypothesis_slots": len(source["hypotheses"]),
        "sidecar_checked_at": source.get("summary", {}).get("checked_at"),
    }


def acquire_rss():
    commit = branch_sha("data")
    raw, sha = read_named(commit, "state.json")
    state = json.loads(raw)
    count = state.get("radar_items")
    require(type(count) is int and count >= 0
            and isinstance(state.get("sha256"), str)
            and HEX64.fullmatch(state["sha256"]), "RSS_CANONICAL_RECEIPT")
    return {"rss_data_commit": commit, "rss_state_blob_sha1": sha,
            "rss_article_count": count, "rss_run_id": str(state.get("run_id", ""))}


def iso(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo:
            return d.astimezone(timezone.utc)
    except ValueError:
        pass
    return None


def source_url(raw):
    if not isinstance(raw, str) or len(raw) > 2000:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None
    return raw


def source_host(raw):
    address = source_url(raw)
    if not address:
        return None
    host = urlsplit(address).hostname.casefold()
    return host.removeprefix("www.")


# The raw S1 named-target extractor can return grammar fragments ("it", "id",
# "technologies increasingly critical"). They must never rank as a product.
# This is a display-layer quality filter: no source hypothesis is deleted.
SINGLE_TERMS = frozenset({
    "haleu", "cowos", "hbm", "dram", "nand", "euv", "cpo", "sic", "gan",
    "uranium", "tungsten", "lithium", "nickel", "cobalt", "graphite",
    "hydrogen", "helium", "ammonia", "silicon", "gallium", "germanium",
    "antimony", "copper", "aniline", "hafnium", "neodymium",
})
BAD_EDGES = frozenset({
    "about", "some", "many", "other", "their", "our", "the", "its", "new",
    "this", "that", "these", "those", "and", "or", "in", "at", "by",
    "with", "from", "how", "what", "where", "when", "why", "who",
    "providing", "supporting", "helping", "aiming", "planned",
    "positioning", "them", "it", "id", "u", "yet", "due", "then",
    "as", "to", "of", "for", "on", "into", "than", "we", "they",
})
BAD_INTERIOR = frozenset({
    "who", "whom", "when", "where", "why", "whose", "our", "their",
    "its", "them", "they", "we", "increasingly", "amid", "were",
    "was", "had", "has", "have", "would", "could", "should",
    "currently", "excluding", "approaching", "manufactured",
    "announced", "exhausted", "weighed", "outlook", "previously",
    "before", "after", "yet", "now", "according",
})
GENERIC_SINGLES = frozenset({
    "it", "id", "them", "and", "ai", "u", "r2", "r3", "n8", "semi",
    "aiming", "helping", "supporting", "providing", "scalable",
    "technologies", "technology", "model", "other", "products",
    "product", "part", "market", "services", "outlook", "equipment",
    "materials", "systems", "applications", "pressure", "electricity",
    "fuel", "turbines", "capacity", "planned", "growth", "peak",
    "reliable", "power", "facility", "supplier", "manufacturer",
    "units", "business", "global", "supply", "demand", "energy",
})


def named_target(value):
    if not isinstance(value, str):
        return None
    result = " ".join(value.split()).strip(" .,:;")
    if not result or len(result) > 140 or result.upper() in ("UNKNOWN", "UNRESOLVED", "NONE"):
        return None
    if result.casefold() in ("미확인", "미분류"):
        return None
    # A trailing coverage year is not a distinct product; preserve the entity.
    result = re.sub(r"\s+in\s+20(?:2[0-9]|3[0-9])$", "", result, flags=re.I)
    words = [word.casefold() for word in result.split()]
    if not words or len(words) > 10:
        return None
    if len(words) == 1:
        key = words[0].strip("-_")
        return result if key in SINGLE_TERMS and key not in GENERIC_SINGLES else None
    if words[0] in BAD_EDGES or words[-1] in BAD_EDGES:
        return None
    # Reject fragments from headline clauses, not named manufactured objects.
    split_words = set(re.findall(r"[A-Za-z]+", result.casefold()))
    if split_words & BAD_INTERIOR:
        return None
    if re.search(r"\b(?:in|on|at|by)\s+(?:20\d\d|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
                 result, re.I):
        return None
    # Prevent vague quantities or incomplete clauses posing as TARGET names.
    if re.match(r"^\d", result) or re.search(r"\b(?:is|are|will|be|can|not)\b", result, re.I):
        return None
    return result


def basic_ranking(source, *, observed_at=None):
    """Rank distinct named TARGETs by unique document IDs and stored signal roles."""
    results = source["results"]
    hypotheses = source["hypotheses"]
    now = observed_at or datetime.now(timezone.utc)
    groups = {}
    hypotheses_considered = 0
    for h in hypotheses.values():
        if not isinstance(h, dict):
            continue
        current = h.get("current")
        if not isinstance(current, dict):
            continue
        target = named_target((current.get("scope") or {}).get("target"))
        if not target:
            continue
        refs = current.get("evidence")
        if not isinstance(refs, list):
            continue
        key = target.casefold()
        entry = groups.setdefault(key, {"target": target, "documents": {}})
        hypotheses_considered += 1
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            docid = ref.get("document_id")
            role = ref.get("role")
            if not isinstance(docid, str) or docid not in results:
                continue
            if not isinstance(role, str) or role.upper() not in ("DEMAND", "SUPPLY", "RELIEF"):
                continue
            doc = results[docid]
            if not isinstance(doc, dict):
                continue
            info = entry["documents"].setdefault(docid, {"roles": set(),
                "body_status": doc.get("body_status"),
                "checked_at": doc.get("checked_at"),
                "url": source_url(doc.get("url")),
                "source": doc.get("source")})
            info["roles"].add(role.upper())

    ranked = []
    for item in groups.values():
        documents = item["documents"]
        if not documents:
            continue
        demand = sum("DEMAND" in d["roles"] for d in documents.values())
        supply = sum("SUPPLY" in d["roles"] for d in documents.values())
        relief = sum("RELIEF" in d["roles"] for d in documents.values())
        full = sum(d["body_status"] == "FULL" for d in documents.values())
        hosts = {host for d in documents.values()
                 if (host := source_host(d["url"])) is not None}
        check_times = [dt for d in documents.values()
                       if (dt := iso(d["checked_at"])) is not None]
        newest = max(check_times) if check_times else None
        days = max(0, (now - newest).total_seconds()/86400) if newest else None
        recency = (10 if days is not None and days <= 2
                   else 7 if days is not None and days <= 7
                   else 3 if days is not None and days <= 30 else 0)
        source_score = 20 if len(hosts) >= 3 else 12 if len(hosts) == 2 else 5 if hosts else 0
        demand_score = min(30, 10*demand)
        supply_score = min(30, 10*supply)
        quality_score = round(10*full / len(documents))
        relief_penalty = min(20, 5*relief)
        score = max(0, min(100, demand_score + supply_score + source_score
                               + recency + quality_score - relief_penalty))
        if not demand or not supply:
            score = min(score, 49)
        urls = sorted({d["url"] for d in documents.values() if d["url"]})[:2]
        ranked.append({"target": item["target"], "score": score,
            "article_count": len(documents), "demand_articles": demand,
            "supply_articles": supply, "relief_articles": relief,
            "full_body_articles": full, "source_hosts": len(hosts),
            "last_checked_at": newest.isoformat() if newest else None,
            "research_level": "수요·공급 양쪽 단서" if demand and supply else "한쪽 또는 부분 단서",
            "example_urls": urls,
            "score_components": {"demand": demand_score, "supply": supply_score,
               "source_diversity": source_score, "last_checked": recency,
               "body_quality": quality_score, "relief_penalty": relief_penalty}})
    ranked.sort(key=lambda x: (-x["score"], -(x["demand_articles"] > 0 and x["supply_articles"] > 0),
                               -x["source_hosts"], -x["article_count"], x["target"].casefold()))
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
    require(len({r["target"].casefold() for r in ranked}) == len(ranked), "DUPLICATE_TARGET")
    return ranked, hypotheses_considered


def evidence_ranking(dashboard, status):
    historical = dashboard.get("counts", {}).get("evidence")
    raw = dashboard.get("sector_rankings", {})
    active = dashboard.get("sector_rankings_live", {})
    require(historical == 511
            and raw.get("ranked_record_count") == 508
            and status.get("historical", {}).get("record_count") == 511
            and status.get("admission", {}).get("eligible_independent_pair_count") == 0
            and active.get("no_verified_supply_shortage_promoted") is True
            and type(active.get("rows")) is list,
            "HISTORICAL_AND_VERIFIED_SOURCE_CLASSIFICATION")
    rows = []
    for item in active["rows"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("BCT_DUAL_RANK_EVIDENCE_ROW_FORMAT")
        n = item.get("evidence_count")
        verified = item.get("rss_verified_count", 0)
        if type(n) is not int or n < 0 or type(verified) is not int or not 0 <= verified <= n:
            raise ValueError("BCT_DUAL_RANK_EVIDENCE_ROW_COUNT")
        rows.append({"sector": item["name"], "evidence_count": n,
                     "historical_count": n-verified,
                     "source_verified_unpaired": verified,
                     "rank": item.get("rank")})
    rows.sort(key=lambda x: (-x["evidence_count"], x["sector"]))
    require(sum(row["historical_count"] for row in rows) == 508
            and sum(row["source_verified_unpaired"] for row in rows)
                == active.get("new_original_verified"),
            "EVIDENCE_AGGREGATE_NOT_IDENTICAL")
    return rows


def _tr_basic(row):
    links = " · ".join("<a target='_blank' rel='noopener noreferrer' href='" +
                       escape(url, quote=True) + "'>기사 원문</a>" for url in row["example_urls"])
    return ("<tr data-search='" + escape(row["target"].casefold(), quote=True) + "'>"
      + "<td>" + str(row["rank"]) + "</td><th scope='row'>" + escape(row["target"]) + "</th>"
      + "<td><strong>" + str(row["score"]) + "</strong><small>/100 · 미확정</small></td>"
      + "<td>" + str(row["demand_articles"]) + "</td><td>" + str(row["supply_articles"]) + "</td>"
      + "<td>" + str(row["relief_articles"]) + "</td>"
      + "<td>" + str(row["article_count"]) + "</td><td>" + str(row["source_hosts"]) + "</td>"
      + "<td>" + str(row["full_body_articles"]) + "</td>"
      + "<td>" + escape(row["research_level"]) + "</td><td>" + links + "</td></tr>")


def _tr_evidence(row):
    return ("<tr data-search='" + escape(row["sector"].casefold(), quote=True) + "'>"
      + "<td>" + str(row["rank"]) + "</td><th scope='row'>" + escape(row["sector"]) + "</th>"
      + "<td><strong>" + str(row["evidence_count"]) + "</strong></td>"
      + "<td>" + str(row["historical_count"]) + "</td>"
      + "<td>" + str(row["source_verified_unpaired"]) + "</td>"
      + "<td>확정된 신규 적격 수급쌍 아님</td></tr>")


def html_page(basic, evidence, report):
    basic_rows = "\n".join(_tr_basic(r) for r in basic[:LIMIT])
    ev_rows = "\n".join(_tr_evidence(r) for r in evidence)
    src = escape(report["sidecar"]["sidecar_commit"][:12])
    generated = escape(report["generated_at_utc"])
    n = lambda x: f"{x:,}"
    return f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#102b51">
<meta name="description" content="BCT 기본분석 선행신호 조사 순위와 원출처 근거 순위를 분리해 제공합니다. 병목 확정 순위가 아닙니다.">
<title>BCT V4 · 두 가지 순위</title>
<style>
:root{{color-scheme:light;font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f9;color:#172b48;line-height:1.55}}
header{{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;background:#102e59;color:white;padding:18px max(16px,calc((100vw - 1350px)/2))}}
header a{{color:white;text-decoration:none;font-weight:650}}main{{max-width:1350px;margin:auto;padding:22px 14px 48px}}
h1{{font-size:clamp(1.5rem,3vw,2.25rem);letter-spacing:-.035em;margin:6px 0 12px}}
.kicker{{font-size:.8rem;color:#345b86;font-weight:750;letter-spacing:.08em}}
.lede{{color:#52647b;max-width:100ch;margin:0 0 16px}}
.tabs{{display:flex;gap:10px;margin:16px 0 18px;flex-wrap:wrap}}
.tabs button{{border:1px solid #bdccdd;border-radius:10px;padding:12px 17px;background:white;color:#18385b;cursor:pointer;font:inherit;font-weight:750}}
.tabs button[aria-selected=true]{{background:#123d77;color:white;border-color:#123d77}}
.tiles{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 20px}}
.tile,.paper{{border:1px solid #c9d8e8;border-radius:12px;background:white}}
.tile{{padding:16px}}.tile small{{display:block;color:#506681;font-weight:600}}
.tile strong{{display:block;font-size:clamp(1.3rem,3vw,2rem);margin:4px 0}}
.tile em{{font-style:normal;color:#61728a;font-size:.8rem}}
.paper{{padding:19px;margin:14px 0}}h2{{font-size:1.23rem;margin:0 0 10px}}
.note{{border-left:4px solid #be8b37;background:#fff8e9;padding:13px 15px;border-radius:8px;margin:14px 0}}
.table-scroll{{overflow-x:auto;border:1px solid #d6e0eb;border-radius:8px}}
table{{width:100%;border-collapse:collapse;min-width:880px;font-size:.89rem}}
th,td{{padding:10px 11px;border-bottom:1px solid #e5ebf2;text-align:left;vertical-align:top}}
thead{{background:#e8eef7}}tbody tr:nth-child(even){{background:#f7f9fc}}
td strong{{font-size:1.05rem}}td small{{display:block;font-size:.75rem;color:#6e7786}}
a{{color:#1c5190}}.filter{{width:min(100%,400px);padding:11px;border:1px solid #9fb4cc;border-radius:8px;font:inherit;margin:6px 0 14px}}
.meta{{color:#607189;font-size:.83rem;overflow-wrap:anywhere}}[hidden]{{display:none!important}}
@media(max-width:700px){{.tiles{{grid-template-columns:repeat(2,minmax(0,1fr))}}.tile,.paper{{padding:12px}}table{{font-size:.85rem}}}}
</style>
</head><body>
<header><strong>BCT V4 · 미래병목 관제</strong><nav><a href="../">메인 화면</a> · <a href="../source-truth/">검증 현황</a></nav></header>
<main><p class="kicker">EARLY SIGNAL PRIORITY · SOURCE-BOUND RESEARCH</p>
<h1>두 가지 순위</h1>
<p class="lede">기본분석에서 발견한 조사 우선순위와 원출처에 연결된 연구 기록 순위를 분리했습니다. 어느 쪽도 적격 수급 부족이 확정된 TARGET 수를 뜻하지 않습니다.</p>
<div class="tabs" role="tablist" aria-label="순위 종류 선택">
<button id="tab-signals" type="button" role="tab" aria-controls="signals" aria-selected="true">① 기본분석 선행신호 순위</button>
<button id="tab-evidence" type="button" role="tab" aria-controls="evidence" aria-selected="false">② 근거 검증 순위</button>
</div>
<section id="signals" role="tabpanel" aria-labelledby="tab-signals">
<div class="tiles">
<div class="tile"><small>기본분석 결과 저장</small><strong>{n(report["sidecar"]["articles_with_screening_result"])}</strong><em>기사별 저장 결과 수</em></div>
<div class="tile"><small>이름 있는 신호 TARGET</small><strong>{n(report["named_targets"])}</strong><em>중복 대상명 병합</em></div>
<div class="tile"><small>가설 슬롯</small><strong>{n(report["sidecar"]["hypothesis_slots"])}</strong><em>확정 대상 수 아님</em></div>
<div class="tile"><small>표시 범위</small><strong>상위 {n(min(LIMIT,len(basic)))}</strong><em>점수 기준 · 조사 우선</em></div>
</div>
<div class="note"><strong>기본분석 점수는 병목 발생확률이 아닙니다.</strong> 기사별 수요·공급 언급, 출처 호스트, 본문 확보 비율, 마지막 분석 확인 시각을 이용한 탐색 점수입니다. 같은 기사 중복은 대상별 한 번만 집계하며, 공급 완화 단서는 감점합니다. 출처 호스트 수는 독립 경제적 사건 검증과 다릅니다.</div>
<div class="paper"><h2>기본분석으로 먼저 조사할 TARGET</h2>
<p class="meta">배점: 수요 30 + 공급 제약 30 + 출처 다양성 20 + 최근 분석 확인 10 + 본문 품질 10 − 공급 완화 최대 20. 수요·공급 중 한쪽만 존재하면 최대 49점. 모든 수치는 미검증 신호입니다.</p>
<input class="filter" id="search-signals" type="search" aria-label="기본분석 순위 TARGET 검색" placeholder="상위 TARGET 검색">
<p id="shown-signals" class="meta">표시 {n(min(LIMIT,len(basic)))}개 / 전체 {n(len(basic))}개</p>
<div class="table-scroll"><table><thead><tr><th>순위</th><th>대상 TARGET</th><th>조사점수</th><th>수요 신호</th><th>공급 신호</th><th>완화 신호</th><th>연결 기사</th><th>출처 호스트</th><th>FULL 본문</th><th>수준</th><th>원문</th></tr></thead><tbody id="rows-signals">{basic_rows}</tbody></table></div></div>
<p class="meta">기준 sidecar 커밋 {src} · 최종 데이터 관찰 기준 {escape(str(report["sidecar"].get("sidecar_checked_at") or "미확인"))}. 본문 인용·추정 판매량·공급 가능 물량을 공개 순위 점수에 넣지 않습니다.</p>
</section>
<section id="evidence" role="tabpanel" aria-labelledby="tab-evidence" hidden>
<div class="tiles">
<div class="tile"><small>과거 연구 기록</small><strong>511</strong><em>2026년 10월 14일 기준</em></div>
<div class="tile"><small>섹터별 과거 기록</small><strong>508</strong><em>분류 외 3건</em></div>
<div class="tile"><small>이번 공개 순위 신규 원출처</small><strong>{n(report["evidence"]["source_verified_unpaired"])}</strong><em>독립 수급쌍 미검증</em></div>
<div class="tile"><small>신규 적격 수급쌍</small><strong>0</strong><em>검증 통과 없음</em></div>
</div>
<div class="note"><strong>이 표는 원출처에 연결된 연구 기록의 규모순입니다.</strong> 과거 511건과 추가 확인된 원출처 기록을 표시하되, 실제 부족량이 입증된 산업 순위나 투자 추천으로 해석하면 안 됩니다.</div>
<div class="paper"><h2>섹터별 원출처 근거 기록 순위</h2>
<input class="filter" id="search-evidence" type="search" aria-label="근거 순위 섹터 검색" placeholder="섹터 검색">
<p id="shown-evidence" class="meta">전체 {n(len(evidence))}개 섹터</p>
<div class="table-scroll"><table><thead><tr><th>순위</th><th>섹터</th><th>합계 기록</th><th>과거 기록</th><th>신규 원출처</th><th>판정</th></tr></thead><tbody id="rows-evidence">{ev_rows}</tbody></table></div></div>
<p class="meta">과거 기록과 신규 검증 자료는 다른 세대입니다. 근거 511건은 과거 스냅샷이며, 증거 단위가 다른 147개 탐색 힌트는 순위 합계에 넣지 않았습니다. <a href="../source-truth/">원출처 검증 현황 상세</a></p>
</section>
<footer class="meta">읽기 전용 · 생성 시각 {generated} · 원본 대시보드 판정/점수/LIVE 변경 없음 · <a href="./report.json">데이터 세대 검증 기록</a></footer>
</main>
<script>
(function(){{
"use strict";
var tabs={{signals:document.getElementById("tab-signals"),evidence:document.getElementById("tab-evidence")}};
function render(){{
 var id=location.hash==="#evidence"?"evidence":"signals";
 for(var k of ["signals","evidence"]){{
  tabs[k].setAttribute("aria-selected",String(k===id));
  document.getElementById(k).hidden=k!==id;
 }}
}}
for(var k of ["signals","evidence"]){{
 (function(kind){{
  tabs[kind].addEventListener("click",function(){{location.hash=kind;render();}});
  var input=document.getElementById("search-"+kind);
  var tbody=document.getElementById("rows-"+kind);
  input.addEventListener("input",function(){{
   var q=input.value.trim().toLocaleLowerCase();
   var count=0;
   for(var tr of tbody.rows){{
    tr.hidden=!tr.getAttribute("data-search").includes(q);
    if(!tr.hidden)count++;
   }}
   document.getElementById("shown-"+kind).textContent="현재 표시 "+count+"개";
  }});
 }})(k);
}}
addEventListener("hashchange",render);
render();
}})();
</script>
</body></html>
"""


def build(site_root, source, sidecar_proof, rss_proof, *, main_sha):
    root = Path(site_root)
    require(isinstance(main_sha, str) and HEX40.fullmatch(main_sha), "MAIN_SHA")
    require(not (root/"rankings").exists(), "DUPLICATE_RANKING_OVERLAY")
    manifest_raw = (root/"build-manifest.json").read_bytes()
    dashboard_raw = (root/"api/dashboard.json").read_bytes()
    js_raw = (root/"app.js").read_bytes()
    page = (root/"index.html").read_text(encoding="utf-8")
    status_raw = (root/"source-truth/status.json").read_bytes()
    manifest = json.loads(manifest_raw)
    dashboard = json.loads(dashboard_raw)
    status = json.loads(status_raw)
    require(manifest.get("site_type") == "PUBLIC_STATIC_READ_ONLY"
            and manifest.get("dashboard_sha256") == sha256(dashboard_raw)
            and manifest.get("evidence_count") == 1703
            and dashboard.get("publication", {}).get("code_commit") == manifest.get("code_commit")
            and dashboard.get("counts", {}).get("evidence") == 511
            and page.count(S7_ANCHOR) == 1
            and page.count(BASIC_ANCHOR) == page.count(EVIDENCE_ANCHOR) == 0,
            "EXISTING_SITE_GENERATION_NOT_VERIFIED")
    require(status.get("historical", {}).get("record_count") == 511
            and status.get("admission", {}).get("eligible_independent_pair_count") == 0,
            "S7_PROTECTED_EVIDENCE_CHANGED")
    basic, hypothesis_named = basic_ranking(source)
    require(len(basic) >= 1, "NO_REAL_BASIC_ANALYSIS_RANK_ROWS")
    evidence = evidence_ranking(dashboard, status)
    require(len(evidence) >= 1, "NO_REAL_EVIDENCE_RANK_ROWS")
    require(sidecar_proof["articles_with_screening_result"] == len(source["results"])
            and sidecar_proof["hypothesis_slots"] == len(source["hypotheses"]),
            "SIDE_SOURCE_PROOF_MISMATCH")
    report = {"format": FORMAT,
        "status": "READONLY_SEPARATE_BASIC_SCREENING_AND_SOURCE_BOUND_RANKS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "main_code_commit": main_sha,
        "legacy_site_code_commit": manifest["code_commit"],
        "legacy_dashboard_sha256": sha256(dashboard_raw),
        "legacy_511_preserved": True,
        "new_strict_pairs_admitted": 0,
        "source_truth_sha256": sha256(status_raw),
        "rss": rss_proof,
        "sidecar": sidecar_proof,
        "named_hypotheses_considered": hypothesis_named,
        "named_targets": len(basic),
        "displayed_targets": min(LIMIT,len(basic)),
        "evidence": {
            "historical_records": 511,
            "historical_sector_records": 508,
            "source_verified_unpaired": sum(x["source_verified_unpaired"] for x in evidence),
            "sectors": len(evidence)},
        "score_weights": {"demand":30,"supply_constraint":30,"source_hosts":20,
                          "checked_recency":10,"full_body_quality":10,
                          "relief_penalty_max":20,"missing_one_side_cap":49},
        "operating_RSS_writes": 0,"operating_sidecar_writes": 0,
        "LIVE_writes": 0,"legacy_rank_writes": 0}
    document = html_page(basic, evidence, report)
    require(BASIC_ANCHOR not in page and EVIDENCE_ANCHOR not in page, "RANK_NAV_ALREADY_ADDED")
    new_main = page.replace(S7_ANCHOR, S7_ANCHOR + "\n        " +
                            BASIC_ANCHOR + "\n        " + EVIDENCE_ANCHOR)
    require(new_main.count(BASIC_ANCHOR) == new_main.count(EVIDENCE_ANCHOR) == 1,
            "RANK_NAV_INSERTION")
    directory = root/"rankings"
    directory.mkdir()
    (directory/"index.html").write_text(document,encoding="utf-8")
    (directory/"report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (root/"index.html").write_text(new_main,encoding="utf-8")
    require((root/"build-manifest.json").read_bytes() == manifest_raw
            and (root/"api/dashboard.json").read_bytes() == dashboard_raw
            and (root/"app.js").read_bytes() == js_raw
            and (root/"source-truth/status.json").read_bytes() == status_raw,
            "PROTECTED_ORIGINAL_CHANGED")
    return {"status":"PASS_DUAL_RANKINGS_READONLY_OVERLAY",
            "html_sha256":sha256((directory/"index.html").read_bytes()),
            "report_sha256":sha256((directory/"report.json").read_bytes()),
            "targets":len(basic),"displayed_targets":min(LIMIT,len(basic)),
            "evidence_sectors":len(evidence),
            "analysis_result_slots":len(source["results"]),
            "historical_511_preserved":True,"new_verified_pairs":0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root",type=Path,required=True)
    parser.add_argument("--main-sha",required=True)
    args = parser.parse_args()
    source,sidecar_proof = acquire_sidecar()
    rss_proof = acquire_rss()
    require(rss_proof["rss_article_count"] >= len(source["results"]),
            "RSS_SIDECAR_COUNT_COMPARISON")
    result = build(args.site_root,source,sidecar_proof,rss_proof,main_sha=args.main_sha)
    print("BCT_DUAL_RANKING_PAGES="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
