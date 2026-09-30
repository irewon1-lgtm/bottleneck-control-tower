import hashlib
import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.candidates import put_candidate
from bct.config import Settings
from bct.countersearch import SEARCH_KINDS, put_countersearch, set_deleted
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.models import AuditLog, CountersearchRun


def test_six_kinds_not_run_and_idempotent_insert(setup):
    _, sf = setup
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        rows = [put_countersearch(session, candidate.id, f"test:{kind}", kind,
                 f"TEST ONLY: search plan for {kind}", note="Not executed")
                for kind in sorted(SEARCH_KINDS)]
        again = [put_countersearch(session, candidate.id, f"test:{kind}", kind,
                 f"TEST ONLY: search plan for {kind}", note="Not executed")
                 for kind in sorted(SEARCH_KINDS)]
        assert [r.id for r in rows] == [r.id for r in again]
        with pytest.raises(ValueError):
            put_countersearch(session, candidate.id, "test:NEW_SUPPLIER", "NEW_SUPPLIER", "different")
        for kind, status, when in (("BAD", "NOT_RUN", None),
                                    ("OTHER", "NOT_RUN", "2026-09-29"),
                                    ("OTHER", "RESULTS_FOUND", None),
                                    ("OTHER", "FAILED", "invalid")):
            with pytest.raises(ValueError):
                put_countersearch(session, candidate.id, "invalid", kind, "test", status, executed_on=when)
    with sf() as session:
        assert session.scalar(select(func.count()).select_from(CountersearchRun)) == 6
        assert {r.search_kind for r in session.scalars(select(CountersearchRun))} == SEARCH_KINDS
        assert all(r.result_status == "NOT_RUN" and r.executed_on is None
                   for r in session.scalars(select(CountersearchRun)))
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "countersearch.created")) == 6


def test_result_date_constraints_soft_delete_restore_and_guards(setup):
    _, sf = setup
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        item = put_countersearch(session, candidate.id, "test:run", "OTHER", "test query",
                                 "INCONCLUSIVE", executed_on="2026-09-29")
        item_id = item.id
        set_deleted(session, item, True)
        with pytest.raises(ValueError):
            put_countersearch(session, candidate.id, "test:run", "OTHER", "test query",
                              "INCONCLUSIVE", executed_on="2026-09-29")
        set_deleted(session, item, False)
        assert put_countersearch(session, candidate.id, "test:run", "OTHER", "test query",
                                 "INCONCLUSIVE", executed_on="2026-09-29").id == item_id
    with sf() as session:
        assert session.get(CountersearchRun, item_id).status == "active"
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.object_id == item_id)) == 3
    with pytest.raises(DatabaseError):
        with sf.begin() as session:
            session.execute(text("DELETE FROM countersearch_runs WHERE id=:id"), {"id": item_id})
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("UPDATE countersearch_runs SET result_status='NOT_RUN' WHERE id=:id"), {"id": item_id})
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("INSERT INTO countersearch_runs (id,candidate_id,record_key,search_kind,query,executed_on,result_status,status,created_at,updated_at) VALUES ('duplicate',:candidate,'test:run','OTHER','test query','2026-09-29','INCONCLUSIVE','active','x','x')"),
                            {"candidate": candidate.id})


def test_stage9_migration_prebackup_and_restore(tmp_path):
    settings = Settings(tmp_path / "store")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0009_actors")
    migration_backup = migrate(settings)
    assert migration_backup is not None and verify_backup(migration_backup)["format"] == 1
    sf = session_factory(settings)
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        put_countersearch(session, candidate.id, "test:new", "NEW_SUPPLIER", "TEST ONLY: query")
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("candidates", "countersearch_runs", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
