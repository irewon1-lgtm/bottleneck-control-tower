#!/usr/bin/env python3
"""BCT session 1: read-only, fixed-snapshot, per-RSS-article status audit.

No network fetching of publisher URLs, AI inference, database updates,
GitHub writes, or canonical article-text export.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit

def git_bytes(ref: str, path: str) -> bytes:
    cmd = ["git", "show", f"{ref}:{path}"]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Unable to read pinned git object: {path}; exit={result.returncode}")
    return result.stdout

def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def numeric_state(path: Path, expected: str, expected_count: int) -> dict:
    payload_hash = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            payload_hash.update(part)
    if payload_hash.hexdigest() != expected:
        raise RuntimeError(f"Database SHA-256 mismatch: {path.name}")
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro&immutable=1", uri=True)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {path.name}")
        count = conn.execute("SELECT count(*) FROM radar_items").fetchone()[0]
        if count != expected_count:
            raise RuntimeError(f"state.json article count mismatch: {path.name}: {count} vs {expected_count}")
        return {"sha256": payload_hash.hexdigest(), "count": count, "integrity": "ok"}
    finally:
        conn.close()

def safe_csv(v):
    if v is None: return ""
    s = str(v).replace("\u0000", "")
    # Excel/Sheets formula injection safeguard
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s

def date_is_after(a, b):
    return bool(a and b and a > b)

def top(counter, n=12):
    return [{"value": str(k), "count": v} for k,v in counter.most_common(n)]

def audit(args):
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    state_raw = git_bytes(args.data_sha, "state.json")
    state = json.loads(state_raw)
    prior = dest / "_previous.sqlite3"
    current = dest / "_canonical.sqlite3"
    current.write_bytes(git_bytes(args.data_sha, "canonical.sqlite3"))
    prior.write_bytes(git_bytes(args.data_sha, "canonical.previous.sqlite3"))
    current_check = numeric_state(current, state["sha256"], state["radar_items"])
    previous_check = numeric_state(prior, state["previous_sha256"], state["previous_radar_items"])
    conn = sqlite3.connect(f"file:{current.resolve()}?mode=ro&immutable=1", uri=True)
    old = sqlite3.connect(f"file:{prior.resolve()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    old.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cols = [r[1] for r in conn.execute("PRAGMA table_info(radar_items)")]
        wanted = ["id","source","external_id","title","url","published_at","collected_at",
                  "snippet","source_type","status","updated_at"]
        if not all(x in cols for x in wanted):
            raise RuntimeError("Unexpected radar_items schema; audit blocked safely")
        rows = [dict(x) for x in conn.execute("SELECT " + ",".join(wanted) + " FROM radar_items ORDER BY id")]
        old_ids = {r[0] for r in old.execute("SELECT id FROM radar_items")}
        ids = {r["id"] for r in rows}
        if len(rows) != len(ids):
            raise RuntimeError("Duplicate radar_items IDs")
        new_ids = ids - old_ids
        lost_ids = old_ids - ids
        source_counter = Counter(x["source"] for x in rows)
        status_counter = Counter(x["status"] for x in rows)
        source_type_counter = Counter(x["source_type"] for x in rows)
        url_counter = Counter(x["url"] for x in rows if x["url"])
        source_identity_counter = Counter((x["source"], x["external_id"]) for x in rows)
        missing = Counter()
        for x in rows:
            for f in ("title","url","snippet","published_at","collected_at","source","external_id"):
                if not (x[f] or "").strip():
                    missing[f] += 1
            if x["url"]:
                p = urlsplit(x["url"])
                if p.scheme not in ("https","http") or not p.hostname:
                    missing["invalid_web_url"] += 1
        article_ids = set(ids)
        if "rss_ai_reviews" in tables:
            ai_rows = [dict(x) for x in conn.execute("SELECT radar_item_id, status, model, prompt_version FROM rss_ai_reviews")]
        else:
            ai_rows = []
        ai_by_id = defaultdict(list)
        for x in ai_rows:
            ai_by_id[x["radar_item_id"]].append(x)
        # Reassemble and SHA-check every immutable sidecar shard, not just its headline counts.
        sys.path.insert(0, str(Path.cwd() / "src"))
        from bct.future_github import assemble
        manifest = json.loads(git_bytes(args.future_sha,"future-candidates.json"))
        if manifest.get("format") != "bct-sharded-sidecar-v1":
            raise RuntimeError("Unrecognized sidecar manifest; no guesses permitted")
        actual_shards = 0
        def load_shard(part):
            nonlocal actual_shards
            raw = git_bytes(args.future_sha, part["path"])
            actual_shards += 1
            return raw
        sidecar = assemble(manifest, load_shard)
        results = sidecar.get("results",{})
        summary = sidecar.get("summary",{})
        if not isinstance(results, dict):
            raise RuntimeError("Results map missing")
        tracking = json.loads(git_bytes(args.future_sha,"future-tracking.json"))
        progress = tracking.get("progress",{})
        if not isinstance(progress, dict):
            progress = {}
        deep_ids = {x.split(":",1)[0] for x in progress if isinstance(x,str)}
        progress_hashes = defaultdict(set)
        for record in progress.values():
            if isinstance(record, dict) and record.get("document_id") and record.get("body_sha256"):
                progress_hashes[record["document_id"]].add(record["body_sha256"])
        current_hash_match = set()
        refs = Counter()
        body = Counter()
        acquisition = Counter()
        decisions = Counter()
        candidates = Counter()
        screen = Counter()
        progress_presence = Counter()
        mismatch = Counter()
        coverage = Counter()
        missing_in_sidecar = []
        orphan_sidecar = sorted(set(results) - ids)
        db_by_id = {x["id"]: x for x in rows}
        for k, x in results.items():
            if k in db_by_id:
                r = db_by_id[k]
                if (x.get("url") or "") != (r.get("url") or ""):
                    mismatch["url_changed_or_missing"] += 1
                if (x.get("title") or "") != (r.get("title") or ""):
                    mismatch["title_changed_or_missing"] += 1
                if (x.get("external_id") or "") != (r.get("external_id") or ""):
                    mismatch["external_id_changed_or_missing"] += 1
        with (dest / "article_status_10365.csv").open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["article_id","source","source_type","url","title","published_at","collected_at",
                "db_status","previous_db_present","sidecar_record_present","sidecar_body_status",
                "sidecar_acquisition_status","sidecar_decision","sidecar_candidate",
                "sidecar_material_check_required","deep_progress_present","deep_progress_same_current_body_hash","rss_ai_review_count","rss_ai_latest_status",
                "sidecar_source","sidecar_source_version","version_checked_at","audit_group"])
            for r in rows:
                k = r["id"]
                x = results.get(k)
                if x is None:
                    missing_in_sidecar.append(k)
                    group = "NO_SIDECAR_RESULT"
                else:
                    coverage["HAS_SIDECAR_RESULT"] += 1
                    b = str(x.get("body_status") or "UNKNOWN")
                    body[b] += 1
                    acquisition[str(x.get("acquisition_status") or "UNKNOWN")] += 1
                    decisions[str(x.get("decision") or "UNKNOWN")] += 1
                    candidates[str(bool(x.get("candidate")))] += 1
                    screen[str(x.get("screening_pending_for") or "")] += 1
                    if b == "FULL":
                        group = "FULL_BODY_WITH_REVIEW_PROGRESS" if k in deep_ids else "FULL_BODY_NO_REVIEW_PROGRESS"
                    elif b == "PARTIAL":
                        group = "PARTIAL_BODY_WITH_REVIEW_PROGRESS" if k in deep_ids else "PARTIAL_BODY_NO_REVIEW_PROGRESS"
                    elif b == "UNAVAILABLE":
                        group = "BODY_UNAVAILABLE"
                    else:
                        group = "BODY_UNKNOWN"
                coverage[group] += 1
                progress_presence[str(k in deep_ids)] += 1
                current_match = bool(x is not None and x.get("body_sha256") and x["body_sha256"] in progress_hashes.get(k,set()))
                if current_match:
                    current_hash_match.add(k)
                reviews = ai_by_id.get(k, [])
                row = [k,r["source"],r["source_type"],r["url"],r["title"],r["published_at"],
                    r["collected_at"],r["status"],k in old_ids,x is not None,
                    x.get("body_status") if x else "",x.get("acquisition_status") if x else "",
                    x.get("decision") if x else "",bool(x.get("candidate")) if x else "",
                    x.get("material_check_required") if x else "",k in deep_ids,current_match,len(reviews),
                    reviews[-1]["status"] if reviews else "",x.get("source") if x else "",
                    x.get("source_version") if x else "",x.get("checked_at") if x else "",group]
                writer.writerow([safe_csv(v) for v in row])
        prior_sidecar_ids = set(results) & old_ids
        new_sidecar_ids = set(results) & new_ids
        research = json.loads(git_bytes(args.data_sha,"v4-public/research.json"))
        acquisition_public = json.loads(git_bytes(args.data_sha,"v4-public/acquisition.json"))
        report = {
            "audit":"BCT_V4_RSS_SESSION1_READ_ONLY_FULL_INVENTORY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope":{"current_data_sha":args.data_sha,"future_sha":args.future_sha,
                     "main_source_sha":args.main_sha, "rss_run_id":state.get("run_id"),
                     "sidecar_checked_at":summary.get("checked_at"),
                     "warning":"Other V4 research paths use distinct populations and are NOT additive."},
            "db":{"current":current_check,"previous":previous_check,
                  "rows":len(rows),"id_unique":len(ids),"ids_added_since_previous":len(new_ids),
                  "ids_removed_since_previous":len(lost_ids),
                  "new_ids":sorted(new_ids),"removed_ids":sorted(lost_ids),
                  "status_counts":dict(status_counter),
                  "source_type_counts":dict(source_type_counter),
                  "distinct_sources":len(source_counter),
                  "top_sources":top(source_counter,15),
                  "missing_field_counts":dict(missing),
                  "exact_url_duplicate_groups":sum(n>1 for n in url_counter.values()),
                  "exact_url_duplicate_excess":sum(n-1 for n in url_counter.values() if n>1),
                  "source_external_identity_duplicates":sum(n-1 for n in source_identity_counter.values() if n>1),
                  "ai_reviews_total":len(ai_rows),
                  "ai_review_articles":len(ai_by_id),
                  "ai_review_status":dict(Counter(x["status"] for x in ai_rows))},
            "sidecar":{"full_manifest_sha256_verified":True,
                       "shards_verified":actual_shards,
                       "result_records_total":len(results),
                       "result_records_in_current_db":len(results.keys() & article_ids),
                       "result_records_not_in_current_db":len(orphan_sidecar),
                       "orphan_result_ids":orphan_sidecar[:100],
                       "db_articles_without_results":len(missing_in_sidecar),
                       "missing_result_ids_sha256":sha256("\n".join(sorted(missing_in_sidecar)).encode()),
                       "missing_result_ids_preview":sorted(missing_in_sidecar)[:20],
                       "new_db_article_with_result":len(new_sidecar_ids),
                       "previous_db_article_with_result":len(prior_sidecar_ids),
                       "source_mismatch":dict(mismatch),
                       "body_status":dict(body),"acquisition_status":dict(acquisition),
                       "decisions":dict(decisions),"candidate":dict(candidates),
                       "screening_pending_for":top(screen,8),
                       "coverage":dict(coverage),
                       "summary_snapshot":{k:summary.get(k) for k in (
                           "db_news_articles","active_processed_total","active_unprocessed_total",
                           "body_ok_total","full_active_total","unavailable_active_total",
                           "candidates_total","screening_pending_total","paired_precursor_documents_total",
                           "closed_failed_sources","checked_at")},
                       "coverage_values_are_distinct_per_article":True},
            "deep_review":{"tracking_progress_entries":len(progress),
                           "unique_document_ids_in_progress":len(deep_ids),
                           "progress_ids_in_current_db":len(deep_ids & ids),
                           "progress_ids_in_sidecar":len(deep_ids & set(results)),
                           "same_current_body_version_reviewed":len(current_hash_match),
                           "historic_progress_without_current_body_hash_match":len((deep_ids & ids)-current_hash_match),
                           "unique_document_ids_with_full_body":sum(
                               x in deep_ids and (results.get(x) or {}).get("body_status")=="FULL" for x in ids),
                           "all_historical_review_events":len(tracking.get("reviews",{})),
                           "review_execution_state":(summary.get("operation_observation") or {}).get("latest",{}).get("review_execution"),
                           "caution":"Progress entries/review events do not mean independent bottleneck verification."},
            "research_separate_path":{"counts":research.get("counts",{}),
                    "as_of":research.get("clocks",{}),"independent_pairs":research.get("counts",{}).get("independent_pairs"),
                    "additional_source_acquisition":acquisition_public.get("counts",{}),
                    "source_integrity_state":acquisition_public.get("source_integrity_state")},
            "findings":[],
        }
        issues = report["findings"]
        if len(new_ids) != state["radar_items"] - state["previous_radar_items"]:
            issues.append("PREVIOUS_CURRENT_ID_DELTA_MISMATCH")
        if lost_ids:
            issues.append("ARTICLES_REMOVED_FROM_LATEST_DATABASE")
        if missing_in_sidecar:
            issues.append("ARTICLES_WITHOUT_SIDECAR_RESULTS")
        if len(new_ids) and len(new_sidecar_ids)==0:
            issues.append("NEWEST_DB_ARTICLES_NOT_YET_PRESENT_IN_SIDECAR")
        if orphan_sidecar:
            issues.append("ORPHAN_SIDECAR_RESULTS")
        if (summary.get("db_news_articles") or 0) != len(rows):
            issues.append("SIDE_CAR_DB_CLOCK_LAG")
        if any(mismatch.values()):
            issues.append("ARTICLE_METADATA_VERSION_DRIFT")
        report["audit_status"] = "PASS_INVENTORY_WITH_OPEN_PROCESSING_GAPS" if not lost_ids and not orphan_sidecar else "NEEDS_RECONCILIATION"
        # Stable, public metadata only; no RSS body or private research artifacts exported.
        (dest/"session1_report.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        summary_lines = [
            "# BCT RSS 세션 1 — 실제 전수 감사",
            "",
            f"- 판정: **{report['audit_status']}**",
            f"- 고정 DB: \`{args.data_sha}\`, 데이터 무결성: **PASS**",
            f"- DB 전체: **{len(rows):,}건**, 이전 대비 추가 **{len(new_ids):,}건**, 삭제 **{len(lost_ids):,}건**",
            f"- sidecar: **{len(results):,}건**, DB 결합 **{len(results.keys() & ids):,}건**, sidecar 결과 없는 기사 **{len(missing_in_sidecar):,}건**",
            f"- sidecar 기준 FULL 본문 **{body['FULL']:,}건**, PARTIAL **{body['PARTIAL']:,}건**, UNAVAILABLE **{body['UNAVAILABLE']:,}건**",
            f"- 심층 검토 진행 기록(고유 문서): **{len(deep_ids & ids):,}건**, 현재 본문 SHA 일치 **{len(current_hash_match):,}건**",
            "- 현재 본문 SHA가 일치하더라도 병목 사실 확정은 아닙니다.",
            f"- RSS AI 리뷰 실제 DB 기록: **{len(ai_rows):,}건**, 고유 문서 **{len(ai_by_id):,}건**",
            f"- 정확한 URL 중복 그룹: **{report['db']['exact_url_duplicate_groups']:,}개**, 초과 기사 **{report['db']['exact_url_duplicate_excess']:,}건**",
            f"- sidecar 원문 검증: **{actual_shards}개 shard SHA-256 + manifest 종합 SHA-256 PASS**",
            "",
            "## 상태별 건수",
            "| 상태 | 건수 |",
            "|---|---:|",
        ]
        for key,count in sorted(coverage.items()):
            if key in {"HAS_SIDECAR_RESULT","NO_SIDECAR_RESULT"}:continue
            summary_lines.append(f"| {key} | {count:,} |")
        summary_lines += ["", "## 확인 필요 사항"]
        summary_lines.extend(f"- {item}" for item in issues)
        summary_lines += [
            "", "주의: 원문 FULL은 의미 분석 완료가 아니며, review progress는 병목 판정 완료가 아닙니다.",
            "이 감사는 원본 DB와 sidecar를 일절 수정하지 않았습니다.",
            "상세 기사별 감사표: article_status_10365.csv",
            "전체 집계와 스냅샷 해시: session1_report.json",
        ]
        (dest/"session1_report.md").write_text("\n".join(summary_lines)+"\n",encoding="utf-8")
        print("SESSION1_SUMMARY_BEGIN")
        print(json.dumps({k:report[k] for k in ("audit_status","scope","db","deep_review","findings")},ensure_ascii=False)[:20000])
        print("SIDECAR_CORE",json.dumps({k:report["sidecar"][k] for k in (
            "full_manifest_sha256_verified","shards_verified","result_records_total",
            "result_records_in_current_db","result_records_not_in_current_db",
            "db_articles_without_results","new_db_article_with_result","body_status",
            "acquisition_status","decisions","candidate","coverage","summary_snapshot")},
             ensure_ascii=False)[:12000])
        print("SESSION1_SUMMARY_END")
        return report
    finally:
        old.close()
        conn.close()
        # No DB copies included in artifact: binary and private content stay in git originals.
        current.unlink(missing_ok=True)
        prior.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-sha",required=True)
    p.add_argument("--future-sha",required=True)
    p.add_argument("--main-sha",required=True)
    p.add_argument("--output",default="session1-output")
    x=p.parse_args()
    audit(x)

if __name__=="__main__":
    main()
