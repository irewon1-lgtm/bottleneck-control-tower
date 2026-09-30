import hashlib
import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.candidates import put_candidate, put_claim, set_deleted
from bct.claim_roles import ROLES, set_claim_role
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.models import AuditLog, Claim


def test_manual_roles_change_query_and_audit(setup):
    _, sf = setup
    with sf.begin() as db:
        candidate = put_candidate(db, "test:srm", "TEST ONLY: SRM", is_test=True)
        claims = [put_claim(db, candidate.id, f"TEST ONLY: hypothesis {i}") for i in range(3)]
        assert [claim.role for claim in claims] == ["OTHER"] * 3
        for claim, role in zip(claims, ("DRIVER", "CONSTRAINT", "RELIEF")):
            set_claim_role(db, claim, role)
            set_claim_role(db, claim, role)
        set_claim_role(db, claims[0], "OTHER")
        set_claim_role(db, claims[0], "DRIVER")
        with pytest.raises(ValueError):
            set_claim_role(db, claims[0], "INVALID")
        set_deleted(db, claims[1], True)
        with pytest.raises(ValueError):
            set_claim_role(db, claims[1], "OTHER")
        set_deleted(db, claims[1], False)
    with sf() as db:
        assert dict(db.execute(select(Claim.role, func.count()).group_by(Claim.role)).all()) == {
            "DRIVER": 1, "CONSTRAINT": 1, "RELIEF": 1}
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "claim.role_changed")) == 5
        assert {row[0] for row in db.execute(select(Claim.role))} <= ROLES
    with pytest.raises(IntegrityError):
        with sf.begin() as db:
            db.execute(text("UPDATE claims SET role='INVALID' WHERE id=:id"), {"id": claims[0].id})


def test_old_claims_backfilled_migration_prebackup_and_restore(tmp_path):
    settings = Settings(tmp_path / "old")
    settings.mkdirs()
    command.upgrade(alembic_config(settings), "0010_countersearch_runs")
    with sqlite3.connect(settings.db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO candidates (id,stable_key,display_name,is_test,status,created_at,updated_at) VALUES ('candidate','test:srm','TEST ONLY: SRM',1,'active','x','x')")
        db.execute("INSERT INTO claims (id,candidate_id,statement,status,created_at,updated_at) VALUES ('claim','candidate','TEST ONLY: unverified','active','x','x')")
    prebackup = migrate(settings)
    assert prebackup is not None and verify_backup(prebackup)["format"] == 1
    with sqlite3.connect(prebackup / "canonical.sqlite3") as db:
        assert "role" not in [row[1] for row in db.execute("PRAGMA table_info(claims)")]
    sf = session_factory(settings)
    with sf.begin() as db:
        claim = db.get(Claim, "claim")
        assert claim.role == "OTHER" and claim.statement == "TEST ONLY: unverified"
        set_claim_role(db, claim, "DRIVER")
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("claims", "candidates", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        assert copy.execute("SELECT role FROM claims WHERE id='claim'").fetchone()[0] == "DRIVER"
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
