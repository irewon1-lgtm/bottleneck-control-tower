import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, DatabaseError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.collector import MalformedRecord, SourceRecord
from bct.config import load_settings
from bct.core import (claim_job, create_freeze, finish_job, get_or_create_job,
                      get_or_create_run, ingest, put_entity, set_deleted, transition_run)
from bct.db import migrate, session_factory
from bct.health import health, rebuild_derived
from bct.models import AuditLog, CollectorRun, Entity, EvidenceFreeze, Job, RawDocument


def test_repeat_source_and_duplicate_document(setup):
    settings, sf = setup
    with sf.begin() as s:
        a = ingest(settings, s, "test", SourceRecord("external-1", b"abc"))
        b = ingest(settings, s, "test", SourceRecord("external-1", b"abc"))
        assert a.id == b.id
        first_id = a.id
    with sf.begin() as s:
        assert ingest(settings, s, "test", SourceRecord("external-1", b"abc")).id == first_id
        assert s.scalar(select(func.count()).select_from(RawDocument)) == 1
        assert s.scalar(select(func.count()).select_from(AuditLog)) == 1
    assert len(list(settings.raw_dir.glob("*/*"))) == 1


def test_same_external_id_changed_content_versions(setup):
    settings, sf = setup
    with sf.begin() as s:
        a = ingest(settings, s, "test", SourceRecord("id", b"v1"))
        b = ingest(settings, s, "test", SourceRecord("id", b"v2"))
        assert a.id != b.id
    with sf.begin() as s:
        assert s.scalar(select(func.count()).select_from(RawDocument)) == 2


def test_missing_optional_id_dedupes_by_hash(setup):
    settings, sf = setup
    with sf.begin() as s:
        a = ingest(settings, s, "test", SourceRecord(None, b"abc"))
        b = ingest(settings, s, "test", SourceRecord(None, b"abc"))
        assert a.id == b.id and a.external_id is None


def test_malformed_input_no_file_or_row(setup):
    settings, sf = setup
    with sf.begin() as s:
        for item in (SourceRecord(None, b""), SourceRecord("", b"x"), SourceRecord(None, "text")):
            with pytest.raises((MalformedRecord, ValueError)):
                ingest(settings, s, "test", item)
    with sf.begin() as s:
        assert not s.scalars(select(RawDocument)).all()
    assert not list(settings.raw_dir.glob("*/*"))


def test_mid_failure_then_rerun_and_transaction_failure(setup):
    settings, sf = setup
    with pytest.raises(RuntimeError):
        with sf.begin() as s:
            ingest(settings, s, "test", SourceRecord("id", b"data"))
            raise RuntimeError("worker crashed before commit")
    with sf.begin() as s:
        assert s.scalar(select(func.count()).select_from(RawDocument)) == 0
        assert s.scalar(select(func.count()).select_from(AuditLog)) == 0
    with sf.begin() as s:
        first = ingest(settings, s, "test", SourceRecord("id", b"data"))
        existing_id = first.id
    with pytest.raises(IntegrityError):
        with sf.begin() as s:
            ingest(settings, s, "test", SourceRecord("id-2", b"new"))
            s.execute(text("INSERT INTO raw_documents (id,source,external_key,sha256,relative_path,byte_size,media_type,created_at,updated_at) VALUES (:id,'test','different','x','x',1,'text','x','x')"), {"id": existing_id})
    with sf.begin() as s:
        assert s.scalar(select(func.count()).select_from(RawDocument)) == 1
        assert s.scalar(select(func.count()).select_from(AuditLog)) == 1
    assert health(settings, deep=True)["ok"]


def test_same_run_repeated_and_failure_retry(setup):
    _, sf = setup
    with sf.begin() as s:
        run = get_or_create_run(s, "stub", "2026-09-29")
        rid = run.id
        assert get_or_create_run(s, "stub", "2026-09-29").id == rid
        transition_run(s, run, "running")
        transition_run(s, run, "failed", "network")
    with sf.begin() as s:
        run = get_or_create_run(s, "stub", "2026-09-29")
        transition_run(s, run, "running")
        transition_run(s, run, "succeeded")
        assert run.attempts == 2
        assert s.scalar(select(func.count()).select_from(CollectorRun)) == 1
        with pytest.raises(ValueError):
            transition_run(s, run, "running")


def test_job_idempotency_retry_lease_and_finished(setup):
    _, sf = setup
    with sf.begin() as s:
        job = get_or_create_job(s, "fetch", "key")
        assert get_or_create_job(s, "fetch", "key").id == job.id
        jid = job.id
        assert claim_job(s, jid, lease_seconds=1)
        assert not claim_job(s, jid)
        assert finish_job(s, jid, error="temporary")
        assert claim_job(s, jid)
        assert finish_job(s, jid)
        assert not claim_job(s, jid)
    with sf.begin() as s:
        job = s.get(Job, jid)
        assert job.attempts == 2 and job.status == "succeeded"


def test_soft_delete_restore_name_change_audit(setup):
    _, sf = setup
    with sf.begin() as s:
        e = put_entity(s, "company", "cik:123", "Old Name")
        eid = e.id
        put_entity(s, "company", "cik:123", "New Name")
        set_deleted(s, e, True)
        with pytest.raises(ValueError):
            put_entity(s, "company", "cik:123", "New Name")
        set_deleted(s, e, False)
        assert e.id == eid and e.deleted_at is None
    with sf.begin() as s:
        assert [e.event for e in s.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id))] == [
            "entity.created", "entity.renamed", "entity.deleted", "entity.restored"]


def test_raw_audit_freeze_immutable_guards(setup):
    settings, sf = setup
    with sf.begin() as s:
        doc = ingest(settings, s, "test", SourceRecord("id", b"evidence"))
        freeze = create_freeze(s, "v1", [doc])
        rid, fid = doc.id, freeze.id
        with pytest.raises(ValueError):
            create_freeze(s, "v1", [doc])
    for statement in (f"UPDATE raw_documents SET source='bad' WHERE id='{rid}'",
                      f"DELETE FROM raw_documents WHERE id='{rid}'",
                      f"UPDATE evidence_freezes SET version='v2' WHERE id='{fid}'",
                      "DELETE FROM audit_log"):
        with pytest.raises(DatabaseError):
            with sf.begin() as s:
                s.execute(text(statement))
    with sf.begin() as s:
        assert s.get(EvidenceFreeze, fid).version == "v1"


def test_migration_and_pre_migration_backup(setup):
    settings, sf = setup
    with sf.begin() as s:
        ingest(settings, s, "test", SourceRecord("id", b"abc"))
    assert migrate(settings) is None  # Repeated init is cheap and idempotent.
    with sqlite3.connect(settings.db_path) as c:
        assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
    assert health(settings, deep=True)["ok"]


def test_migration_backs_up_existing_database(tmp_path):
    from bct.config import Settings
    settings = Settings(tmp_path / "legacy")
    settings.mkdirs()
    with sqlite3.connect(settings.db_path) as c:
        c.execute("CREATE TABLE unrelated (key TEXT)")
        c.execute("INSERT INTO unrelated VALUES ('old')")
    backup = migrate(settings)
    assert backup is not None and verify_backup(backup)["format"] == 1
    with sqlite3.connect(backup / "canonical.sqlite3") as c:
        assert c.execute("SELECT key FROM unrelated").fetchone()[0] == "old"
    assert health(settings)["ok"]


def test_external_id_cannot_collide_with_missing_id(setup):
    settings, sf = setup
    digest = hashlib.sha256(b"same").hexdigest()
    with sf.begin() as s:
        a = ingest(settings, s, "test", SourceRecord(None, b"same"))
        b = ingest(settings, s, "test", SourceRecord("content:" + digest, b"same"))
        assert a.id != b.id
    assert len(list(settings.raw_dir.glob("*/*"))) == 1


def test_backup_restore_and_corruption_rejected(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as s:
        ingest(settings, s, "test", SourceRecord(None, b"abc"))
    backup = create_backup(settings)
    restored = restore_backup(backup, tmp_path / "recovered")
    restored_settings = type(settings)(restored)
    assert health(restored_settings, deep=True)["ok"]
    with pytest.raises(FileExistsError):
        restore_backup(backup, restored)
    blob = next((backup / "raw").glob("sha256/*/*"))
    blob.chmod(0o644)
    blob.write_bytes(b"tampered")
    with pytest.raises(IOError):
        restore_backup(backup, tmp_path / "recovered2")
    assert not (tmp_path / "recovered2").exists()


def test_derived_can_rebuild_and_health_detects_corruption(setup):
    settings, sf = setup
    with sf.begin() as s:
        ingest(settings, s, "test", SourceRecord("id", b"abc"))
    assert rebuild_derived(settings) == 1
    index = settings.derived_dir / "raw_index.json"
    first = index.read_bytes()
    index.unlink()
    assert rebuild_derived(settings) == 1 and index.read_bytes() == first
    blob = next(settings.raw_dir.glob("*/*"))
    blob.chmod(0o644)
    blob.write_bytes(b"corrupt")
    assert not health(settings, deep=True)["ok"]
    with pytest.raises(IOError):
        with sf.begin() as s:
            ingest(settings, s, "test", SourceRecord("id-2", b"abc"))


def test_config_validation(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("storage_root: ./data\njob_lease_seconds: 30\n", encoding="utf-8")
    assert load_settings(config).root == tmp_path / "data"
    config.write_text("database_name: ../escape.sqlite3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(config)
