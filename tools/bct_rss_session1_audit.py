#!/usr/bin/env python3
"""Read-only BCT session 1: account for each RSS article against independent sidecars."""
import argparse
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def normalize_url(raw):
    try:
        p = urlsplit(raw or "")
        host = (p.hostname or "").lower()
        if not host:
            return ""
        query = urlencode(sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                                 if k.lower() not in TRACKING and not k.lower().startswith("utm_")))
        return urlunsplit((p.scheme.lower(), host + ((":"+str(p.port)) if p.port else ""),
                           p.path.rstrip("/") or "/", query, ""))
    except Exception:
        return ""

def read_snapshot(db_path):
    conn = sqlite3.connect("file:" + str(db_path.resolve()) + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity_check failed"
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "radar_items" in tables
    rows = [dict(r) for r in conn.execute("SELECT * FROM radar_items ORDER BY id")]
    counts = {}
    for t in sorted(tables):
        if t.startswith(("rss_", "radar_", "future_", "evidence", "claim", "candidate")):
            counts[t] = conn.execute('SELECT COUNT(*) FROM "' + t.replace('"','""') + '"').fetchone()[0]
    reviews = {}
    if "rss_ai_reviews" in tables:
        for r in conn.execute("SELECT radar_item_id, status, model, prompt_version FROM rss_ai_reviews"):
            reviews.setdefault(r[0], []).append({"status":r[1], "model":r[2], "prompt_version":r[3]})
    conn.close()
    return rows, counts, reviews

def read_future(manifest_path, future_sha):
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert m.get("format") == "bct-sharded-sidecar-v1", "Unexpected future-candidates storage format"
    data, summary = {}, {}
    total_items = 0
    shard_receipts = []
    for info in m["shards"]:
        path = info["path"]
        assert path.startswith("future-candidates.shards/") and ".." not in path
        raw = subprocess.check_output(["git", "show", future_sha + ":" + path])
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == info["sha256"], "sidecar shard SHA256 mismatch: " + path
        doc = json.loads(raw)
        entries = doc.get("items", [])
        assert len(entries) == info["item_count"], "sidecar item count mismatch: " + path
        total_items += len(entries)
        for item in entries:
            field, key, value = item["field"], item["key"], item["value"]
            if field == "results":
                assert key not in data, "duplicate result ID: " + key
                data[key] = value
            elif field == "summary":
                summary[key] = value
        shard_receipts.append({"path": path, "count":len(entries), "sha256":digest})
    assert total_items == m["total_item_count"], "sidecar total_item_count mismatch"
    return data, summary, shard_receipts

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--previous-db", required=True, type=Path)
    p.add_argument("--state", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--data-sha", required=True)
    p.add_argument("--future-sha", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    state = json.loads(a.state.read_text(encoding="utf-8"))
    assert sha256_file(a.db) == state["sha256"], "current DB SHA256 mismatch"
    assert sha256_file(a.previous_db) == state["previous_sha256"], "previous DB SHA256 mismatch"
    articles, table_counts, reviews = read_snapshot(a.db)
    prior, _, _ = read_snapshot(a.previous_db)
    assert len(articles) == state["radar_items"], "state.json article count does not match DB"
    assert len(prior) == state["previous_radar_items"], "previous article count mismatch"
    assert len({r["id"] for r in articles}) == len(articles), "duplicate article UUID"
    records, prev_summary, shard_receipts = read_future(a.manifest, a.future_sha)
    current_ids = {r["id"] for r in articles}
    matched = current_ids.intersection(records)
    missing = current_ids - records.keys()
    orphan = records.keys() - current_ids
    source_ct = Counter(); record_states = Counter(); body_ct = Counter()
    decision_ct = Counter(); acquisition_ct = Counter(); reason_ct = Counter()
    processed_ct = Counter(); url_ct = Counter(); normalized_url_ct = Counter()
    rss_ai_status = Counter()
    rows = []
    for r in articles:
        aid = r["id"]; z = records.get(aid); url = r.get("url") or ""
        source_ct[r.get("source") or "UNKNOWN"] += 1
        if url: url_ct[url] += 1
        nurl = normalize_url(url)
        if nurl: normalized_url_ct[nurl] += 1
        rs = reviews.get(aid, [])
        for v in rs: rss_ai_status[v["status"]] += 1
        if z is None:
            body = "NOT_IN_SIDECAR"; decision = "NOT_IN_SIDECAR"
            acquisition = "NOT_IN_SIDECAR"; why = ["NO_RESULT_IN_SIDECAR"]
            classification = "NO_SIDECAR_RESULT"
        else:
            body = str(z.get("body_status") or "UNKNOWN")
            decision = str(z.get("decision") or "UNKNOWN")
            acquisition = str(z.get("acquisition_status") or "UNKNOWN")
            why = z.get("reasons") or []
            if not isinstance(why, list): why=[str(why)]
            if body in ("FULL","PARTIAL"):
                classification = "BODY_PRESENT_RESULT_RECORDED"
            elif body == "UNAVAILABLE":
                classification = "BODY_UNAVAILABLE"
            else:
                classification = "BODY_STATE_UNKNOWN"
        record_states["MATCHED" if z is not None else "MISSING"] += 1
        body_ct[body] += 1; decision_ct[decision] += 1
        acquisition_ct[acquisition] += 1; processed_ct[classification] += 1
        for why_code in why: reason_ct[str(why_code)] += 1
        rows.append({
            "article_id": aid, "source":r.get("source") or "", "source_type":r.get("source_type") or "",
            "url":url, "published_at":r.get("published_at") or "", "collected_at":r.get("collected_at") or "",
            "rss_status":r.get("status") or "", "title":r.get("title") or "",
            "has_rss_snippet":bool((r.get("snippet") or "").strip()),
            "sidecar_matched":z is not None, "body_status":body, "body_chars":(z or {}).get("body_chars") or 0,
            "acquisition_status":acquisition, "decision":decision, "candidate":bool((z or {}).get("candidate")),
            "provenance_verified":bool((z or {}).get("provenance_verified")),
            "publication_verified":bool((z or {}).get("publication_verified")),
            "analysis_checked_at":(z or {}).get("checked_at") or "",
            "reason_codes":";".join(map(str,why)),
            "rss_ai_review_count":len(rs),
            "rss_ai_review_statuses":";".join(v["status"] for v in rs),
            "session1_status":classification
        })
    assert len(rows) == len(articles)
    assert sum(record_states.values()) == len(articles)
    fields=list(rows[0]) if rows else []
    ledger=a.out/"article_ledger.csv"
    with ledger.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    counts = {
        "data_articles":len(articles),
        "previous_articles":len(prior),
        "new_since_previous_snapshot":len(articles)-len(prior),
        "article_sidecar_match":len(matched),
        "article_without_sidecar":len(missing),
        "sidecar_result_ids_absent_from_current_db":len(orphan),
        "sidecar_result_entries":len(records),
        "article_source_count":len(source_ct),
        "rss_ai_distinct_articles":len(reviews),
        "rss_ai_status_rows":dict(rss_ai_status),
        "rss_missing_published_at":sum(not r.get("published_at") for r in articles),
        "rss_missing_snippet":sum(not (r.get("snippet") or "").strip() for r in articles),
        "rss_status":dict(Counter(r.get("status") or "UNKNOWN" for r in articles)),
        "exact_duplicate_url_groups":sum(v>1 for v in url_ct.values()),
        "exact_duplicate_url_extra_records":sum(v-1 for v in url_ct.values() if v>1),
        "normalized_url_duplicate_groups":sum(v>1 for v in normalized_url_ct.values()),
        "normalized_url_duplicate_extra_records":sum(v-1 for v in normalized_url_ct.values() if v>1),
        "sidecar_record_coverage_pct":round(100*len(matched)/len(articles),2) if articles else 0,
    }
    keys=("db_news_articles","active_processed_total","active_unprocessed_total","body_ok_total",
          "full_active_total","unavailable_active_total","candidates_total","screening_pending_total",
          "paired_precursor_documents_total","closed_failed_sources","checked_at")
    published={k:prev_summary.get(k) for k in keys}
    operation=prev_summary.get("operation_observation") or {}
    latest=operation.get("latest") or {}
    published["operation_latest"]={k:latest.get(k) for k in
       ("completed_documents","review_documents_total","pending_total","failed_total","material_pending",
        "quick_pending","automatic_s3_total","review_execution","observed_at")}
    report={
        "format":"BCT_RSS_SESSION1_AUDIT_V1",
        "audited_at_utc":datetime.now(timezone.utc).isoformat(),
        "repo":"irewon1-lgtm/bottleneck-control-tower",
        "data_sha":a.data_sha, "future_sha":a.future_sha,
        "state_run_id":state.get("run_id"),
        "sqlite_integrity":"PASS_CURRENT_AND_PREVIOUS",
        "state_hash_validation":"PASS_CURRENT_AND_PREVIOUS",
        "shards_validated":len(shard_receipts),
        "sidecar_manifest_integrity":"PASS",
        "counts":counts,
        "sidecar_summary_as_published":published,
        "article_status_classification":dict(processed_ct),
        "body_status_by_current_article":dict(body_ct),
        "decision_by_current_article":dict(decision_ct),
        "acquisition_status_by_current_article":dict(acquisition_ct),
        "reason_code_counts":dict(reason_ct),
        "top_article_sources":source_ct.most_common(30),
        "sqlite_table_row_counts":table_counts,
        "ledger":{"file":ledger.name, "rows":len(rows), "sha256":sha256_file(ledger)},
        "limitations":[
            "A successful title/snippet signal screen is not a full-body semantic review.",
            "Sidecar is a separate eventually-consistent snapshot; snapshot drift is shown, not hidden.",
            "FULL/PARTIAL describe body availability, not independently verified bottlenecks.",
            "Duplicate normalized URLs are leads, not automatic deletions.",
            "Session 1 does not change canonical data or promote candidates."
        ]
    }
    (a.out/"session1_summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    handoff={
      "session":"2","data_sha_at_audit":a.data_sha,"future_sha_at_audit":a.future_sha,
      "article_total":len(articles),
      "body_unavailable":body_ct.get("UNAVAILABLE",0),
      "no_sidecar_result":len(missing),
      "unknown_body_status":sum(v for k,v in body_ct.items() if k not in ("FULL","PARTIAL","UNAVAILABLE","NOT_IN_SIDECAR")),
      "top_reasons":reason_ct.most_common(30),
      "instructions":"Recover missing full originals by cause; keep existing verified bodies; preserve lineage and existing statuses."
    }
    (a.out/"session2_handoff.json").write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=(
        "# BCT RSS 세션 1 — 고정 스냅샷 전수 감사\n\n"
        f"- DB SHA: {a.data_sha}\n- 미래 후보 SHA: {a.future_sha}\n"
        f"- SQLite 무결성 / 원본 해시: **PASS**\n"
        f"- RSS 기사: **{len(articles):,}건** (이전 DB {len(prior):,}건)\n"
        f"- 미래 분석 결과 연결: **{len(matched):,}건**, 미연결 **{len(missing):,}건**\n"
        f"- 원문 FULL: **{body_ct['FULL']:,}건**, PARTIAL: **{body_ct['PARTIAL']:,}건**, "
        f"UNAVAILABLE: **{body_ct['UNAVAILABLE']:,}건**\n"
        f"- RSS AI 별도 검토 연결: **{len(reviews):,}개 기사**\n"
        f"- 동일 URL 초과 중복 후보: **{counts['exact_duplicate_url_extra_records']:,}건**"
        " (삭제 금지, 원문 확인 필요)\n"
        f"- 데이터 시차: sidecar 기록 당시 {published.get('db_news_articles')}, 현재 {len(articles)}\n"
        f"- 산출물: 기사별 대장 {len(rows):,}행 / 요약 JSON / 다음 세션 인계서\n\n"
        "본 수치는 서로 다른 독립 처리 경로의 기록입니다. 병목 확정 또는 AI 정밀 검토 완료와 동일하지 않습니다.\n"
    )
    (a.out/"session1_report.md").write_text(md,encoding="utf-8")
    print("BCT_SESSION1_AUDIT",json.dumps({
        "status":"PASS","data_sha":a.data_sha,"future_sha":a.future_sha,
        "counts":counts,
        "current_body":dict(body_ct),"current_decisions":decision_ct.most_common(15),
        "top_reasons":reason_ct.most_common(12),
        "source_top10":source_ct.most_common(10),
        "sidecar_published":published,
        "ledger_sha256":report["ledger"]["sha256"]
    },ensure_ascii=False),flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f: f.write(md)

if __name__=="__main__":
    main()
