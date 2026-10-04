import hashlib
import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from bct.actors import ACTOR_TYPES, link_document, put_actor, set_deleted
from bct.backup import create_backup, restore_backup, verify_backup
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.models import Actor, ActorDocument, AuditLog
from test_candidates import _documents


def test_actor_types_three_document_links_and_repeat(setup):
    settings, sf = setup
    ids = _documents(settings, sf)
    with sf.begin() as session:
        actors = [put_actor(session, f"test:actor:{kind}", f"TEST ONLY: {kind}", kind, is_test=True)
                  for kind in sorted(ACTOR_TYPES)]
        actor = next(a for a in actors if a.actor_type == "OTHER")
        links = [link_document(session, actor.id, source, doc_id)
                 for source, doc_id in zip(("sec", "usaspending", "federal_register"), ids)]
        assert put_actor(session, actor.stable_key, actor.display_name, "OTHER", is_test=True).id == actor.id
        assert [link_document(session, actor.id, source, doc_id).id
                for source, doc_id in zip(("sec", "usaspending", "federal_register"), ids)] == [l.id for l in links]
        with pytest.raises(ValueError):
            put_actor(session, "test:invalid", "invalid", "UNLISTED", is_test=True)
    with sf() as session:
        assert session.scalar(select(func.count()).select_from(Actor)) == 6
        assert session.scalar(select(func.count()).select_from(ActorDocument)) == 3
        assert {a.actor_type for a in session.scalars(select(Actor))} == ACTOR_TYPES
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "actor_document.linked")) == 3


def test_soft_delete_restore_and_database_constraints(setup):
    settings, sf = setup
    sec, award, _ = _documents(settings, sf)
    with sf.begin() as session:
        actor = put_actor(session, "test:actor", "TEST ONLY", "OTHER", is_test=True)
        link = link_document(session, actor.id, "sec", sec)
        actor_id, link_id = actor.id, link.id
        set_deleted(session, link, True)
        set_deleted(session, actor, True)
        with pytest.raises(ValueError):
            link_document(session, actor_id, "usaspending", award)
        with pytest.raises(ValueError):
            set_deleted(session, link, False)
        set_deleted(session, actor, False)
        set_deleted(session, link, False)
        assert link_document(session, actor_id, "sec", sec).id == link_id
        with pytest.raises(ValueError):
            link_document(session, actor_id, "sec", "missing")
    with sf() as session:
        assert session.get(Actor, actor_id).status == "active"
        assert session.get(ActorDocument, link_id).deleted_at is None
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event.in_(["actor.deleted", "actor.restored",
                                  "actor_document.deleted", "actor_document.restored"]))) == 4
    for table in ("actor_documents", "actors"):
        with pytest.raises(DatabaseError):
            with sf.begin() as session:
                session.execute(text(f"DELETE FROM {table}"))
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("UPDATE actors SET actor_type='INVALID' WHERE id=:id"), {"id": actor_id})
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("INSERT INTO actor_documents (id,actor_id,sec_document_id,contract_award_id,status,created_at,updated_at) VALUES ('bad',:actor,:sec,:award,'active','x','x')"),
                            {"actor": actor_id, "sec": sec, "award": award})


def test_stage8_migration_backup_and_restore(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0008_lineages")
    migration_backup = migrate(settings)
    assert migration_backup is not None and verify_backup(migration_backup)["format"] == 1
    sf = session_factory(settings)
    sec, _, _ = _documents(settings, sf)
    with sf.begin() as session:
        actor = put_actor(session, "test:actor", "TEST ONLY", "OTHER", is_test=True)
        link_document(session, actor.id, "sec", sec)
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("actors", "actor_documents", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
