"""Local, read-only V4 research dashboard. No collector, model, or operating writes.

Run: python -m bct.v4.dashboard --repo . --port 8765
The existing research DB is opened with mode=ro. On a clean checkout only, the
verified committed research backup is restored to a separate dashboard cache.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlsplit


ASSETS = Path(__file__).with_name("dashboard_web")
SECTORS = {
    "Defense and space": "방산·항공우주",
    "Power grid generation": "전력·발전",
    "Semiconductor AI datacenter": "반도체·광통신·AI 기반시설",
    "Manufacturing industrial equipment": "제조·산업설비",
    "Minerals metals rare earths": "광물·금속·희토류",
    "Oil gas chemicals": "석유·가스·화학",
    "Logistics ports shipping": "물류·항만·해운",
    "Automotive batteries": "자동차·배터리",
    "Construction infrastructure": "건설·기반시설",
    "Biopharma supply chain": "바이오·의약",
    "Energy and nuclear": "에너지·원자력",
    "Energy cross-sector (EIA)": "에너지 통계",
    "UNCLASSIFIED_OPEN_DISCOVERY": "아직 분류하지 않은 산업",
}
ROLES = {
    "DEMAND_INCREASE": "수요 증가", "SUPPLY_INCREASE": "공급 증가",
    "SUPPLY_DECREASE": "공급 감소", "SUPPLY_DELAY": "공급 지연",
    "RELIEF": "공급 부담 완화", "UNKNOWN": "역할 확인 필요",
    "SUPPLY_DECREASE_REPORTED": "공급 감소로 보고됨",
    "SUPPLY_READINESS_REPORTED": "가동 전환으로 보고됨",
}
MISSING = {
    "CUSTOMER_NEED_PERIOD": "고객이 제품을 필요로 하는 시기",
    "SUPPLIER_READY_PERIOD": "공급자가 납품할 수 있는 시기",
    "TOTAL_QUALIFIED_SUPPLY": "조건을 충족하는 전체 공급량",
    "RESIDUAL_DEMAND": "취소·감소를 반영한 남은 수요",
    "INDEPENDENT_COMPARABLE_COUNTERPART": "같은 대상에 대한 독립적인 반대편 근거",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def known(value):
    return value not in (None, "", "UNKNOWN")


def public_link(value):
    if not isinstance(value, str):
        return None
    try:
        u = urlsplit(value)
        if u.scheme not in ("https", "http") or not u.hostname or u.username or u.password:
            return None
        if re.search(r"(?:token|auth|session|password|secret|key)=", u.query, re.I):
            return None
        return value
    except ValueError:
        return None


@lru_cache(maxsize=2)
def workbook_records(path, modified_ns, size, period, url):
    """Cache the existing parser by file version; no network or source writes."""
    from .structured_changes import snapshot
    raw = gzip.decompress(Path(path).read_bytes())
    return snapshot(raw, period, url)


class DataUnavailable(ValueError):
    pass


class ResearchReader:
    def __init__(self, repo, database=None):
        self.repo = Path(repo).resolve()
        self.reports = self.repo / "docs/v4/cross-industry"
        self.path = Path(database).resolve() if database else self.repo / "var/v4/cross-industry/ledger/v4.sqlite3"
        self.mode = "연구 데이터베이스"
        self.snapshot = False
        if not self.path.is_file():
            if database:
                raise DataUnavailable("지정한 연구 데이터베이스를 찾을 수 없습니다.")
            self._restore()
        with self.connection() as db:
            if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != ("bct-v4-ledger-1",):
                raise DataUnavailable("V4 연구 데이터베이스 형식이 아닙니다.")

    def _restore(self):
        archive = self.reports / "research-snapshot.sqlite3.gz"
        try:
            packed = archive.read_bytes()
            if digest(packed) != read_json(self.reports / "verification.json")["snapshot_file_sha256"]:
                raise DataUnavailable("연구 백업 파일의 해시가 검증 기록과 다릅니다.")
            raw = gzip.decompress(packed)
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise DataUnavailable("검증된 연구 백업을 읽을 수 없습니다.") from exc
        cache = self.repo / "var/v4/dashboard"
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / (digest(raw) + ".sqlite3")
        if not target.exists():
            fd, name = tempfile.mkstemp(dir=cache, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                os.replace(name, target)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        elif digest(target.read_bytes()) != digest(raw):
            raise DataUnavailable("복원된 연구 백업이 변경되었습니다. 새 복원 경로가 필요합니다.")
        self.path, self.snapshot = target, True
        self.mode = "검증된 연구 백업의 읽기 전용 복사본"

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            yield db
        finally:
            db.close()

    def _state(self, db):
        records, events, reviews = {}, [], {}
        for seq, at, kind, payload in db.execute("SELECT seq,at,kind,payload FROM events ORDER BY seq"):
            item = json.loads(payload)
            if kind in ("CROSS_COMMON_EVIDENCE", "CROSS_COMMON_EVIDENCE_REVISION"):
                records[item["event_id"]] = item
            elif kind == "CROSS_DEEP_REVIEW":
                reviews[item["source_event_id"]] = item
            events.append((at, kind, item))
        return records, events, reviews

    def _industry_maps(self):
        report = read_json(self.reports / "analysis.json")
        docs = {r["document_id"]: r.get("industry_hint") for r in report["documents"]}
        originals = {r["record_id"]: r.get("industry_hint") for r in report["research_review_queue"]}
        return report, docs, originals

    def _row(self, r, docs, originals):
        category = "reviewed" if r["event_status"] == "ADOPTED_RESEARCH_EVENT" else "structured" if r["evidence_kind"] == "STRUCTURED" else "discovery"
        hint = originals.get(r["original_record_id"]) or next((docs.get(s.get("document_id")) for s in r["sources"] if docs.get(s.get("document_id"))), None)
        if category == "structured":
            hint = "Power grid generation"
        status = {"reviewed": "별도 AI 원문 검토 · 사람 검증 전", "structured": "공식 표의 변화 · 실제 공급 확인 전", "discovery": "제품·관계 검토 대기"}[category]
        actuality = {"ACTUAL": "실제 사건", "PLAN": "계획", "NEGATED": "부정된 사건", "UNKNOWN": "사실 여부 확인 필요", "REPORTED_STATUS_NOT_PHYSICALLY_VERIFIED": "보고된 상태"}.get(r["actuality"], "사실 여부 확인 필요")
        fields = r.get("fields", {})
        need = fields.get("need_time") or fields.get("customer_need_time")
        ready = fields.get("ready_time") or fields.get("supply_ready_time")
        def surface(value):
            return value.get("surface") if isinstance(value, dict) else value
        return {"id": r["event_id"], "category": category, "product": r["source_surface_target"].get("product") or "제품명 확인 필요",
                "industry": SECTORS.get(hint, "산업 확인 필요"), "industry_basis": "저장된 출처 분류이며 제품의 산업 확정은 아닙니다.",
                "role": r["role"], "role_label": ROLES.get(r["role"], "역할 확인 필요"),
                "stage": r["s_stage"], "status": status, "actuality": actuality,
                "target": r["source_surface_target"], "need_time": surface(need), "ready_time": surface(ready), "evidence_period": surface(fields.get("period")),
                "period": "예상 시기 미확인", "published_at": next((s.get("published_at") for s in r["sources"] if known(s.get("published_at"))), None),
                "source_count": len(r["sources"]), "sources": [{"url": public_link(s.get("url")), "published_at": s.get("published_at"), "acquired_at": s.get("acquired_at")} for s in r["sources"]],
                "future_gap": r["future_gap"], "independence": r["independence"], "is_future_candidate": False}

    def dashboard(self):
        with self.connection() as db:
            records, events, reviews = self._state(db)
            report, doc_industries, originals = self._industry_maps()
            rows = [self._row(r, doc_industries, originals) for r in records.values()]
            rows.sort(key=lambda r: ({"reviewed": 0, "discovery": 1, "structured": 2}[r["category"]], r["product"].casefold(), r["id"]))
            source_results = [x for _, k, x in events if k == "CROSS_SOURCE_RESULT"]
            article_results = [x for _, k, x in events if k == "CROSS_ARTICLE_RESULT"]
            latest_articles = {x["url"]: x for x in article_results}
            source_latest = {x["source"]["url"]: x for x in source_results}
            discovered = {x["url"] for _, k, x in events if k == "CROSS_DISCOVERED"}
            captures = [x for x in latest_articles.values() if x["status"] == "CAPTURED"]
            run_rows = [(at, json.loads(t)) for at, t in db.execute("SELECT at,payload FROM runs ORDER BY at")]
            collections = [(at, r) for at, r in run_rows if r.get("version") == "bct-cross-industry-1"]
            last = collections[-1] if collections else (None, {})
            categories = Counter(r["category"] for r in rows)
            # The saved analysis reports a frozen scope, not all subsequent rows.
            coverage = {"at": report["at"], "documents": report["reading_documents"],
                        "read_characters": sum(d["read_characters"] for d in report["documents"]),
                        "body_characters": sum(d["body_characters"] for d in report["documents"])}
            sectors = {}
            for r in source_results:
                name = SECTORS.get(r["source"]["industry_hint"], "산업 확인 필요")
                c = sectors.setdefault(name, {"name": name, "sources": 0, "source_errors": 0, "bodies": 0, "read_documents": 0})
                c["sources"] += r["status"] == "PARSED"
                c["source_errors"] += r["status"] != "PARSED"
            for r in captures:
                name = SECTORS.get(r["industry_hint"], "산업 확인 필요")
                sectors.setdefault(name, {"name": name, "sources": 0, "source_errors": 0, "bodies": 0, "read_documents": 0})["bodies"] += r.get("body_characters", 0) > 0
            for key, value in report["industry_counters"].items():
                name = SECTORS.get(key, "산업 확인 필요")
                sectors.setdefault(name, {"name": name, "sources": 0, "source_errors": 0, "bodies": 0, "read_documents": 0})["read_documents"] = value.get("reading_documents", 0)
            errors = []
            for r in source_results + article_results:
                if r["status"] == "FAILED_ISOLATED":
                    err = r.get("error") or {}
                    reason = "접근이 거부되었습니다. 사이트와 중간 연결 중 어느 쪽의 제한인지는 미확인입니다." if err.get("http_status") == 403 else "수집 자료의 형식 또는 날짜를 읽지 못했습니다." if err.get("category") == "C_EXTRACTION_OR_VALIDATION" else "통신 또는 자료 처리 오류가 기록되었습니다."
                    errors.append({"at": r["at"], "url": public_link(r.get("url") or r["source"]["url"]), "step": "출처 목록" if "source" in r else "본문 확보", "message": reason, "http_status": err.get("http_status"), "action": "자동 재시도 없이 분리 보관"})
            quarantined = [x for _, k, x in events if k == "CROSS_BODY_VIEW_QUARANTINED"]
            progress = read_json(self.repo / "docs/v4/PROGRESS.json")
            current = progress.get("cross_industry", {})
            auth = progress.get("authentication_resume", {})
            quality = progress.get("quality_improvement", {})
            comparison = progress.get("path_comparison", {})
            final = comparison.get("final", {})
            ai_history = [
                {"name": "인증 회복 후 판독", "at": auth.get("at"), "attempted": auth.get("cumulative_evaluation_attempted"),
                 "received": auth.get("cumulative_evaluation_received"), "scope": "기존 동결 평가 누적 기록",
                 "notes": [f"빈 응답 {auth.get('processing', {}).get('empty_model_responses', '미확인')}건",
                           f"원문 검증 거부 항목 {auth.get('processing', {}).get('source_rejected_items', '미확인')}개",
                           "인증 회복은 당시 기록이며 현재 키를 재시험하지 않았습니다."]},
                {"name": "문맥 판독 개선 시험", "at": quality.get("at"), "attempted": quality.get("new_Groq_calls"),
                 "received": quality.get("received"), "scope": "별도 개선 시험 범위",
                 "notes": [f"HTTP 400 오류 {quality.get('HTTP400', '미확인')}건",
                           f"미호출 평가 문서 {quality.get('unattempted', '미확인')}건",
                           "실패한 요청과 기존 점수는 보존하고 반복 호출하지 않았습니다."]},
                {"name": "대체 판독 경로 최종 비교", "at": comparison.get("at"), "attempted": final.get("new_Groq_generations"),
                 "received": final.get("responses"), "scope": "최종 비교만 집계 · 별도 호환 시험 제외",
                 "notes": [f"출력 묶음 처리 실패 {final.get('packet_failure', '미확인')}건",
                           f"공통 채점 문서 {final.get('common_scored_documents', '미확인')}건",
                           "정확도와 누락 기준을 충족하지 못해 AI 자동 판독을 보류했습니다."]},
            ]
            return {"schema": "bct-v4-dashboard-1", "loaded_at": datetime.now(timezone.utc).isoformat(),
                    "data_at": max([at for at, _, _ in events] + [at for at, _ in run_rows], default=None),
                    "source": {"mode": self.mode, "snapshot": self.snapshot, "read_only": True},
                    "counts": {"evidence": len(rows), **{k: categories[k] for k in ("reviewed", "structured", "discovery")},
                               "discovered_urls": len(discovered), "source_attempts": len(source_results),
                               "source_success": sum(r["status"] == "PARSED" for r in source_results),
                               "source_errors": sum(r["status"] != "PARSED" for r in source_results),
                               "article_attempts": len(article_results), "captured": len(captures),
                               "body_status": dict(Counter(r["body_status"] for r in captures)),
                               "body_nonempty": sum(r.get("body_characters", 0) > 0 for r in captures),
                               "article_errors": sum(r["status"] != "CAPTURED" for r in article_results),
                               "pending": last[1].get("pending_unattempted"), "quarantined": len(quarantined),
                               "s1_signals": sum(r["stage"] == "S1" for r in rows),
                               "future_candidates": report["future_12_36_month_candidates"]},
                    "coverage": coverage, "sectors": list(sectors.values()), "records": rows,
                    "candidate_scope": "저장된 전 산업 연구 평가 범위의 12~36개월 후보 집계입니다. 이 화면은 새 후보 판정을 하지 않습니다.",
                    "automation": {"scope_at": current.get("at"), "collection_runs": len(collections),
                                   "last_collection_at": last[0], "last_cpu_at": max((at for at, r in run_rows if "CPU_reading" in r), default=None),
                                   "last_review_at": max((at for at, k, _ in events if k == "CROSS_DEEP_REVIEW"), default=None),
                                   "collection_mode": current.get("automation", {}).get("collection"),
                                   "ai_mode": current.get("automation", {}).get("AI_reader"),
                                   "shadow_mode": current.get("automation", {}).get("Shadow"),
                                   "api_calls": current.get("Groq_new_calls"), "api_tokens": current.get("Groq_new_tokens"),
                                   "api_cost_krw": current.get("API_cost_KRW"), "platform_cost": None,
                                   "ai_history": ai_history,
                                   "reviews": len(reviews), "errors": sorted(errors, key=lambda e: e["at"], reverse=True),
                                   "runs": [{"at": at, "source_attempts": r["sources_executed"], "article_attempts": r["article_attempts"], "captured": len(r["captured"]), "pending": r["pending_unattempted"]} for at, r in reversed(collections)]}}

    def evidence(self, event_id):
        with self.connection() as db:
            records, _, reviews = self._state(db)
            r = records.get(event_id)
            if r is None:
                raise KeyError(event_id)
            _, docs, originals = self._industry_maps()
            result = self._row(r, docs, originals)
            references = []
            for ref in r["references"]:
                if r["evidence_kind"] == "STRUCTURED":
                    references.append(self._structured_ref(ref))
                    continue
                d = db.execute("SELECT payload FROM documents WHERE id=?", (ref.get("document_id"),)).fetchone()
                doc = json.loads(d[0]) if d else None
                a, b, quote = ref.get("start"), ref.get("end"), ref.get("quote")
                valid = bool(doc and isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= len(doc["body"])
                             and digest(doc["body"].encode()) == ref.get("body_sha256") == doc["body_sha256"]
                             and doc["origin_url"] == ref.get("origin_url") and doc["body"][a:b] == quote)
                references.append({"kind": "text", "quote": quote, "start": a, "end": b,
                                   "body_sha256": ref.get("body_sha256"), "url": public_link(ref.get("origin_url")),
                                   "published_at": ref.get("published_at"), "acquired_at": doc.get("acquired_at") if doc else ref.get("acquired_at"),
                                   "verified": valid, "verification": "저장된 원문·해시·위치 일치" if valid else "저장된 원문과 일치를 확인하지 못함",
                                   "context_before": doc["body"][max(0, a-180):a] if valid else None,
                                   "context_after": doc["body"][b:b+180] if valid else None,
                                   "document_characters": len(doc["body"]) if doc else None})
            missing = reviews.get(event_id, {}).get("missing", [])
            result.update(references=references, fields=r.get("fields", {}),
                          missing=[MISSING.get(k, "추가 근거 확인") for k in missing] or ["필요 시기, 적격 공급량과 독립적인 반대편 근거를 확인해야 합니다."],
                          all_references_verified=bool(references) and all(x["verified"] for x in references),
                          semantic_note="인용 일치는 의미 정확도나 미래 병목의 증명이 아닙니다.",
                          counterpart_note="같은 제품·규격·지역·기간·공급 자격을 충족한 독립적인 수요·공급 근거쌍은 확인되지 않았습니다.")
            return result

    def _structured_ref(self, ref):
        """Use the existing XLSX parser; independently recheck saved row and cells."""
        filename = {"2026-06": "june2026.xlsx.gz", "2026-07": "july2026.xlsx.gz"}.get(ref.get("period"))
        valid = False
        if filename:
            try:
                path = self.repo / "docs/v4/path-comparison/structured-native" / filename
                stat = path.stat()
                parsed = workbook_records(str(path), stat.st_mtime_ns, stat.st_size, ref["period"], ref["url"])
                if parsed["raw_sha256"] == ref.get("raw_sha256"):
                    native = parsed["records"].get(tuple(ref["id"]))
                    valid = bool(native and all(native.get(k) == ref.get(k) for k in ("sheet", "xml_path", "row", "fields", "cells")))
            except (OSError, ValueError, KeyError):
                pass
        return {"kind": "table", "verified": valid, "verification": "보존된 공식 표의 행·셀·해시 일치" if valid else "보존된 공식 표와 일치를 확인하지 못함",
                "url": public_link(ref.get("url")), "period": ref.get("period"), "row": ref.get("row"), "sheet": ref.get("sheet"),
                "raw_sha256": ref.get("raw_sha256"), "fields": ref.get("fields", {}), "cells": ref.get("cells", {})}


def make_server(reader, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Do not log URL parameters, original text, or credentials.

        def send(self, status, body, content_type="application/json; charset=utf-8", download=False):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="bct-v4-research.json"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            host = self.headers.get("Host", "").split(":")[0]
            if host not in ("localhost", "127.0.0.1"):
                self.send(403, {"error": "로컬 연구 화면에서만 접근할 수 있습니다."})
                return
            path = urlsplit(self.path).path
            try:
                if path in ("/api/dashboard", "/api/export"):
                    self.send(200, reader.dashboard(), download=path == "/api/export")
                elif re.fullmatch(r"/api/evidence/[a-f0-9]{64}", path):
                    self.send(200, reader.evidence(path.rsplit("/", 1)[1]))
                elif path == "/api/health":
                    with reader.connection() as db:
                        db.execute("SELECT COUNT(*) FROM events").fetchone()
                    self.send(200, {"status": "연구 자료 연결됨", "read_only": True})
                elif path in ("/", "/index.html", "/app.js", "/style.css"):
                    name = "index.html" if path == "/" else path[1:]
                    kind = {"html": "text/html", "js": "text/javascript", "css": "text/css"}[name.rsplit(".", 1)[1]]
                    self.send(200, (ASSETS / name).read_bytes(), kind + "; charset=utf-8")
                else:
                    self.send(404, {"error": "요청한 화면이나 근거를 찾을 수 없습니다."})
            except KeyError:
                self.send(404, {"error": "이 근거 기록을 찾을 수 없습니다."})
            except (sqlite3.Error, OSError, ValueError):
                self.send(503, {"error": "연구 자료를 읽지 못했습니다. 데이터베이스와 연구 보고서 연결을 확인해 주세요."})

        def do_POST(self):
            self.send(405, {"error": "읽기 전용 화면입니다. 실행이나 자료 변경은 지원하지 않습니다."})

        do_PUT = do_POST
        do_DELETE = do_POST

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="BCT V4 한국어 연구 대시보드 · 읽기 전용")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="저장소 경로")
    parser.add_argument("--database", type=Path, help="선택: 기존 V4 연구 SQLite 경로")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        reader = ResearchReader(args.repo, args.database)
        server = make_server(reader, args.port)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.exit(1, "연구 화면을 시작하지 못했습니다: " + (str(exc) if isinstance(exc, DataUnavailable) else "연구 자료 형식 또는 실행 포트를 확인해 주세요.") + "\n")
    print(f"BCT V4 연구 화면 시작 · 로컬 포트 {server.server_port} · {reader.mode} · 읽기 전용", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
