import hashlib
import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.lineages import link_document, put_lineage, set_deleted
from bct.models import AuditLog, Lineage, LineageDocument
from test_candidates import _documents


def test_one_test_lineage_three_document_types_and_idempotency(setup):
    settings, sf = setup
    ids = _documents(settings, sf)
    with sf.begin() as session:
        lineage = put_lineage(session, "test:stage8:group", "TEST ONLY: same group not verified", is_test=True)
        links = [link_document(session, lineage.id, source, doc_id)
                 for source, doc_id in zip(("sec", "usaspending", "federal_register"), ids)]
        assert put_lineage(session, "test:stage8:group", "TEST ONLY: same group not verified", is_test=True).id == lineage.id
        assert [link_document(session, lineage.id, source, doc_id).id
                for source, doc_id in zip(("sec", "usaspending", "federal_register"), ids)] == [l.id for l in links]
    with sf() as session:
        assert session.scalar(select(func.count()).select_from(Lineage)) == 1
        assert session.scalar(select(func.count()).select_from(LineageDocument)) == 3
        assert session.get(Lineage, lineage.id).is_test is True
        assert {l.id for l in session.scalars(select(LineageDocument).where(
            LineageDocument.lineage_id == lineage.id))} == {l.id for l in links}
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "lineage_document.linked")) == 3


def test_soft_delete_restore_and_invalid_links(setup):
    settings, sf = setup
    sec, award, _ = _documents(settings, sf)
    with sf.begin() as session:
        lineage = put_lineage(session, "test:stage8:group", "TEST ONLY: group", is_test=True)
        link = link_document(session, lineage.id, "sec", sec)
        lineage_id, link_id = lineage.id, link.id
        set_deleted(session, link, True)
        set_deleted(session, lineage, True)
        with pytest.raises(ValueError):
            link_document(session, lineage_id, "usaspending", award)
        with pytest.raises(ValueError):
            set_deleted(session, link, False)
        set_deleted(session, lineage, False)
        set_deleted(session, link, False)
        assert link_document(session, lineage_id, "sec", sec).id == link_id
        with pytest.raises(ValueError):
            link_document(session, lineage_id, "sec", "missing")
    with sf() as session:
        assert session.get(Lineage, lineage_id).status == "active"
        assert session.get(LineageDocument, link_id).deleted_at is None
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event.in_(["lineage.deleted", "lineage.restored",
                                  "lineage_document.deleted", "lineage_document.restored"]))) == 4
    for table in ("lineage_documents", "lineages"):
        with pytest.raises(DatabaseError):
            with sf.begin() as session:
                session.execute(text(f"DELETE FROM {table}"))
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("INSERT INTO lineage_documents (id,lineage_id,sec_document_id,contract_award_id,status,created_at,updated_at) VALUES ('bad',:lineage,:sec,:award,'active','x','x')"),
                            {"lineage": lineage_id, "sec": sec, "award": award})


def test_stage7_migration_backup_and_restore(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0007_evidence")
    migration_backup = migrate(settings)
    assert migration_backup is not None and verify_backup(migration_backup)["format"] == 1
    sf = session_factory(settings)
    sec, _, _ = _documents(settings, sf)
    with sf.begin() as session:
        lineage = put_lineage(session, "test:stage8:group", "TEST ONLY: group", is_test=True)
        link_document(session, lineage.id, "sec", sec)
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("lineages", "lineage_documents", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
