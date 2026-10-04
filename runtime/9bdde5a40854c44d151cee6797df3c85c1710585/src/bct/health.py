import hashlib
import json
import os
import tempfile

from sqlalchemy import select, text
from .config import Settings
from .db import alembic_config, engine_for, session_factory
from alembic.script import ScriptDirectory
from .models import RawDocument


def health(settings: Settings, *, deep: bool = False) -> dict:
    issues = []
    if not settings.db_path.exists():
        return {"ok": False, "issues": ["database missing; run init"], "raw_count": 0}
    engine = engine_for(settings)
    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        integrity = conn.execute(text("PRAGMA quick_check")).scalar()
    if revision != ScriptDirectory.from_config(alembic_config(settings)).get_current_head():
        issues.append(f"unexpected migration revision: {revision}")
    if integrity != "ok":
        issues.append(f"SQLite integrity: {integrity}")
    count = 0
    with session_factory(settings)() as session:
        for doc in session.scalars(select(RawDocument)):
            count += 1
            path = settings.root / "raw" / doc.relative_path
            if not path.is_file() or (deep and hashlib.sha256(path.read_bytes()).hexdigest() != doc.sha256):
                issues.append(f"missing or corrupted raw: {doc.id}")
    return {"ok": not issues, "issues": issues, "raw_count": count, "revision": revision}


def rebuild_derived(settings: Settings) -> int:
    """A disposable index, deterministically regenerated from canonical records."""
    settings.mkdirs()
    with session_factory(settings)() as session:
        docs = session.scalars(select(RawDocument).order_by(RawDocument.id)).all()
        entries = [{"id": d.id, "source": d.source, "sha256": d.sha256} for d in docs]
    fd, temp = tempfile.mkstemp(prefix="index-", dir=settings.staging_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(entries, file, ensure_ascii=False, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, settings.derived_dir / "raw_index.json")
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return len(entries)
