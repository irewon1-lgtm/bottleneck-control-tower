"""One private SQLite ledger; atomic append-only evidence and frozen firsts."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from bct.objective_lock import objective_binding, require_objective


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encode(value).encode()).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class Ledger:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "v4.sqlite3"
        if self.path.exists():
            # Inspect read-only BEFORE issuing any write or PRAGMA.
            with sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True) as probe:
                try:
                    row = probe.execute("SELECT value FROM metadata WHERE key='format'").fetchone()
                except sqlite3.DatabaseError as exc:
                    raise ValueError("UNOWNED_DATABASE: V4 refuses an existing non-V4 DB") from exc
                if row != ("bct-v4-ledger-1",):
                    raise ValueError("UNOWNED_DATABASE")
        self.db = sqlite3.connect(self.path, timeout=30)
        self.path.chmod(0o600)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS blobs(id TEXT PRIMARY KEY, data BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, url TEXT NOT NULL,
                raw_id TEXT REFERENCES blobs(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS captures(seq INTEGER PRIMARY KEY, url TEXT NOT NULL,
                doc_id TEXT REFERENCES documents(id), at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS readings(id TEXT PRIMARY KEY,
                doc_id TEXT REFERENCES documents(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, at TEXT NOT NULL,
                mode TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS firsts(mode TEXT NOT NULL, target_id TEXT NOT NULL,
                first_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(mode,target_id));
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at TEXT NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('format','bct-v4-ledger-1')")
            binding = encode(objective_binding())
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('objective',?)", (binding,))
            if self.db.execute("SELECT value FROM metadata WHERE key='objective'").fetchone()[0] != binding:
                raise ValueError("OBJECTIVE_LEDGER_MISMATCH")
            for table in ("metadata", "blobs", "documents", "captures", "readings", "runs", "firsts", "events"):
                for op in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS protect_{table}_{op} BEFORE {op} ON {table} "
                                    "BEGIN SELECT RAISE(ABORT,'append-only V4 ledger'); END")

    def close(self):
        self.db.close()

    @contextmanager
    def worker(self):
        with (self.root / ".worker.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                self.recover()
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def event(self, kind, payload):
        self.db.execute("INSERT INTO events(at,kind,payload) VALUES(?,?,?)", (now(), kind, encode(payload)))

    def recover(self):
        opened = {}
        for kind, text in self.db.execute("SELECT kind,payload FROM events ORDER BY seq"):
            data = json.loads(text)
            if kind == "RUN_STARTED":
                opened[data["run_id"]] = data
            elif kind in ("RUN_FINISHED", "RUN_INTERRUPTED"):
                opened.pop(data["run_id"], None)
        with self.db:
            for run_id in opened:
                self.event("RUN_INTERRUPTED", {"run_id": run_id, "reason": "worker restarted before completion"})
        return len(opened)

    def capture(self, doc, raw=None, reading=None):
        if hashlib.sha256(doc["body"].encode()).hexdigest() != doc["body_sha256"]:
            raise ValueError("BODY_HASH_MISMATCH")
        raw_id = hashlib.sha256(raw).hexdigest() if raw is not None else None
        if raw_id is not None and raw_id != doc.get("raw_sha256"):
            raise ValueError("RAW_HASH_MISMATCH")
        with self.db:
            if raw is not None:
                self.db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (raw_id, raw))
            old = self.db.execute("SELECT payload FROM documents WHERE id=?", (doc["document_id"],)).fetchone()
            if old and any(json.loads(old[0]).get(k) != doc.get(k) for k in ("origin_url", "raw_sha256", "body_sha256")):
                raise ValueError("DOCUMENT_ID_COLLISION")
            self.db.execute("INSERT OR IGNORE INTO documents VALUES(?,?,?,?)",
                            (doc["document_id"], doc["origin_url"], raw_id, encode(doc)))
            if reading is not None:
                self.db.execute("INSERT OR IGNORE INTO readings VALUES(?,?,?)",
                                (sha([doc["document_id"], reading]), doc["document_id"], encode(reading)))
            self.db.execute("INSERT INTO captures(url,doc_id,at) VALUES(?,?,?)",
                            (doc["origin_url"], doc["document_id"], now()))
        return old is None

    def latest_documents(self):
        return [json.loads(r[0]) for r in self.db.execute("""
            SELECT d.payload FROM documents d JOIN captures c ON c.doc_id=d.id
            WHERE c.seq=(SELECT MAX(c2.seq) FROM captures c2 WHERE c2.url=c.url)
            ORDER BY c.seq
        """)]

    def save_run(self, run_id, result, mode):
        require_objective(result)
        with self.db:
            # Idempotent retry; never generate a second first observation.
            previous = self.db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
            if previous:
                return json.loads(previous[0])
            for candidate in result.get("candidates", []):
                tid = candidate["target_id"]
                first = self.db.execute("SELECT first_at FROM firsts WHERE mode=? AND target_id=?", (mode, tid)).fetchone()
                if first:
                    candidate["candidate_first_detected_at"] = first[0]
                else:
                    self.db.execute("INSERT INTO firsts VALUES(?,?,?,?)",
                                    (mode, tid, candidate["candidate_first_detected_at"], encode(candidate)))
            self.db.execute("INSERT INTO runs VALUES(?,?,?,?)", (run_id, now(), mode, encode(result)))
            self.event("RUN_FINISHED", {"run_id": run_id, "mode": mode})
        return result

    def history(self, mode="LIVE"):
        runs = [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM runs WHERE mode=? ORDER BY at,id", (mode,))]
        latest = {c["target_id"]: c for c in (runs[-1].get("candidates", []) if runs else [])}
        output = []
        for tid, at, payload in self.db.execute("SELECT target_id,first_at,payload FROM firsts WHERE mode=?", (mode,)):
            candidate = latest.get(tid)
            output.append({"first": json.loads(payload), "first_at": at,
                           "latest": candidate, "state": "OPEN" if candidate else "UNKNOWN_OR_REFUTED_SEE_RUN_HISTORY"})
        return output

    def backup(self, destination):
        path = Path(destination)
        if path.exists():
            raise ValueError("BACKUP_DESTINATION_EXISTS")
        if path.resolve() == self.path:
            raise ValueError("BACKUP_OVERWRITE")
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as target:
            self.db.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("BACKUP_INTEGRITY_FAILED")
        path.chmod(0o600)

    def status(self):
        runs = self.db.execute("SELECT at,payload FROM runs WHERE mode='LIVE' ORDER BY at").fetchall()
        # Only successful actual network acquisitions count as observed LIVE days.
        days = sorted({at[:10] for at, text in runs if json.loads(text).get("live_captured", 0) > 0})
        return {"integrity": self.db.execute("PRAGMA integrity_check").fetchone()[0],
                "documents": self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
                "runs": self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
                "observed_live_days": days, "shadow_7_days": "BLOCKED",
                "reason": "7-day continuity and new-document/target/failure/recovery review still required",
                "early_success_cases": 0, "forecast_performance": "BLOCKED"}
