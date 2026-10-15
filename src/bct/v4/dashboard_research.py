"""Read-only, source-checked projection of the separate CPU recovery ledger.

Does not promote candidates, run models, collect URLs or write a research DB.
"""
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3


def sha(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def load_recovery(repo):
    root = Path(repo) / "docs/v4/cpu-recovery"
    if not root.exists():
        return None
    paths = [root / n for n in ("research-snapshot.sqlite3.gz", "storage-proof.json", "RESULTS.json")]
    signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    return _load(str(root), signature)


@lru_cache(maxsize=3)
def _load(root_path, signature):
    root = Path(root_path)
    packed = (root / "research-snapshot.sqlite3.gz").read_bytes()
    proof = json.loads((root / "storage-proof.json").read_text())
    result = json.loads((root / "RESULTS.json").read_text())
    if sha(packed) != proof["snapshot_sha256"]:
        raise ValueError("CPU 연구 백업 해시 불일치")
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(gzip.decompress(packed))
        db.execute("PRAGMA query_only=ON")
        if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != ("bct-v4-ledger-1",):
            raise ValueError("CPU 연구 DB 형식 불일치")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, expected in proof["tables"].items():
            if table not in tables or not table.replace("_", "").isalnum():
                raise ValueError("CPU 보존 표 불일치")
            rows = db.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            values = [[v.hex() if isinstance(v, bytes) else v for v in row] for row in rows]
            if len(rows) != expected["rows"] or sha(values) != expected["sha256"]:
                raise ValueError("CPU 보존 표 내용 불일치: " + table)
        docs = {id_: json.loads(payload) for id_, payload in db.execute("SELECT id,payload FROM documents")}
        for d in docs.values():
            if sha(d["body"].encode()) != d["body_sha256"]:
                raise ValueError("CPU 원문 본문 해시 불일치")
        records, details = [], {}

        def text_ref(doc, ref):
            a, b = ref["start"], ref["end"]
            quote = ref["quote"]
            if not (isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= len(doc["body"]) and doc["body"][a:b] == quote):
                raise ValueError("CPU 연구 인용 위치 불일치")
            from .dashboard import public_link
            return {"kind": "text", "quote": quote, "start": a, "end": b,
                    "body_sha256": doc["body_sha256"], "url": public_link(doc["origin_url"]),
                    "published_at": doc.get("published_at"), "acquired_at": doc.get("acquired_at"),
                    "verified": True, "verification": "저장된 원문·해시·위치 일치",
                    "context_before": doc["body"][max(0, a-180):a], "context_after": doc["body"][b:b+180],
                    "document_characters": len(doc["body"])}

        def append_record(id_, doc, product, category, role, refs, explanation):
            from .dashboard import ROLES
            references = [text_ref(doc, ref) for ref in refs]
            row = {"id": id_, "category": category, "product": product,
                   "industry": "산업 추가 확인", "industry_basis": "별도 CPU 연구 범위이며 산업을 확정하지 않았습니다.",
                   "role": role, "role_label": ROLES.get(role, "역할 확인 필요"),
                   "stage": "UNKNOWN", "status": "새 보도 검토 · 공식 1차 확인 전" if category == "reported" else "CPU 제품 표기 제안 · 의미 검증 전",
                   "actuality": "기사 보도 · 공식 확인 전" if category == "reported" else "사실 여부 확인 필요",
                   "target": {"product": product, "specification": None, "region": None, "customer_group": None, "supply_pool": None},
                   "need_time": None, "ready_time": None, "evidence_period": None,
                   "period": "예상 시기 미확인", "published_at": doc.get("published_at"),
                   "source_count": 1, "sources": [{k: references[0].get(k) for k in ("url", "published_at", "acquired_at")}],
                   "future_gap": "UNKNOWN", "independence": "UNKNOWN", "is_future_candidate": False,
                   "research_scope": "cpu-recovery"}
            records.append(row)
            details[id_] = {**row, "references": references, "fields": {}, "missing": [explanation,
                "공식 1차 원문·고객 필요 시기·전체 적격 공급·독립 반대편 근거 확인이 필요합니다."],
                "all_references_verified": True,
                "semantic_note": "인용 일치는 제품 분류·사건 의미·미래 병목의 검증이 아닙니다.",
                "counterpart_note": "연구 제안을 기존 엔진에 채택하거나 S1/S2/S3 후보로 승격하지 않았습니다."}

        for at, kind, payload in db.execute("SELECT at,kind,payload FROM events ORDER BY seq"):
            r = json.loads(payload)
            if kind == "CPU_WINDOW_RESULT":
                doc = docs[r["document_id"]]
                for index, span in enumerate(r.get("CPU", {}).get("spans", [])):
                    if span["label"] != "product":
                        continue
                    if span["body_sha256"] != doc["body_sha256"]:
                        raise ValueError("CPU 제안의 원문 버전 불일치")
                    append_record(sha(["cpu-recovery", r["key"], index]), doc, span["text"], "cpu_product", "UNKNOWN",
                                  [{**span["locator"], "quote": span["text"]}],
                                  "CPU가 제품이라고 제안한 원문 표기입니다. 중복·비제품·관계 오분류 가능성을 포함해 보존했습니다.")
            elif kind == "RECOVERY_NEW_SOURCE_REPORTED_EVENT_REVIEW":
                if r["s_stage"] != "UNKNOWN" or r["candidates"] or not r["research_only"]:
                    raise ValueError("새 보도 검토의 후보 승격 경계 위반")
                doc = docs[r["source_document_id"]]
                if r["body_sha256"] != doc["body_sha256"] or r["raw_sha256"] != doc["raw_sha256"]:
                    raise ValueError("새 보도 검토 원문 버전 불일치")
                append_record(r["id"], doc, r["product"]["surface"], "reported", r["role"], r["references"], r["original_review"]["reason_ko"])
        products = sum(r["category"] == "cpu_product" for r in records)
        reported = sum(r["category"] == "reported" for r in records)
        if products != result["CPU_product_proposals_retained"] or reported != result["new_source_reported_actual_event_reviews"]:
            raise ValueError("CPU 연구 집계와 실제 DB 불일치")
        return {"at": result["at"], "snapshot_sha256": sha(packed),
                "summary": {k: result[k] for k in ("documents_processed", "first_CPU_documents", "previous_partial_document_expanded", "body_characters", "actually_CPU_read_characters", "unread_characters", "unread_nonwhitespace_characters", "CPU_product_proposals_retained", "new_source_reported_actual_event_reviews", "new_official_primary_verified_events", "strict_downstream_event_adoptions", "AI_quality", "independent20", "S1_S2_S3_change")},
                "records": records, "details": details}
    finally:
        db.close()
