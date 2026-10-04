import hashlib
import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, DatabaseError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.candidates import link_document, put_candidate, put_claim
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.evidence import record_evidence, revise_evidence, set_deleted
from bct.health import health
from bct.models import AuditLog, Claim, ClaimDocumentLink, Evidence
from test_candidates import _documents


def _linked(settings, sf):
    ids = _documents(settings, sf)
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        claims = [put_claim(session, candidate.id, f"TEST ONLY: hypothesis {i}") for i in range(3)]
        links = [link_document(session, claim.id, source, doc_id)
                 for claim, source, doc_id in zip(claims, ("sec", "usaspending", "federal_register"), ids)]
        return [link.id for link in links]


def test_three_directions_lookup_and_duplicate_prevention(setup):
    settings, sf = setup
    links = _linked(settings, sf)
    with sf.begin() as session:
        items = [record_evidence(session, link_id, direction, "TEST ONLY: structural check")
                 for link_id, direction in zip(links, ("SUPPORT", "CONTRADICT", "NEUTRAL"))]
        assert record_evidence(session, links[0], "SUPPORT", "TEST ONLY: structural check").id == items[0].id
        with pytest.raises(ValueError):
            record_evidence(session, links[0], "CONTRADICT", "changed")
        with pytest.raises(ValueError):
            record_evidence(session, links[1], "INVALID")
    with sf() as session:
        rows = session.execute(select(Evidence.direction, Claim.id, ClaimDocumentLink.id)
            .join(ClaimDocumentLink, Evidence.claim_document_link_id == ClaimDocumentLink.id)
            .join(Claim, ClaimDocumentLink.claim_id == Claim.id)).all()
        assert len(rows) == 3 and {r[0] for r in rows} == {"SUPPORT", "CONTRADICT", "NEUTRAL"}
        assert {r[2] for r in rows} == set(links)
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "evidence.created")) == 3


def test_revision_soft_delete_restore_and_database_guards(setup):
    settings, sf = setup
    link_id = _linked(settings, sf)[0]
    with sf.begin() as session:
        item = record_evidence(session, link_id, "NEUTRAL")
        evidence_id = item.id
        revise_evidence(session, item, "SUPPORT", "TEST ONLY: correction")
        set_deleted(session, item, True)
        with pytest.raises(ValueError):
            record_evidence(session, link_id, "SUPPORT", "TEST ONLY: correction")
        set_deleted(session, item, False)
        assert record_evidence(session, link_id, "SUPPORT", "TEST ONLY: correction").id == evidence_id
    with sf() as session:
        assert session.get(Evidence, evidence_id).status == "active"
        events = [e.event for e in session.scalars(select(AuditLog).where(
            AuditLog.object_id == evidence_id).order_by(AuditLog.created_at))]
        assert events == ["evidence.created", "evidence.revised", "evidence.deleted", "evidence.restored"]
    with pytest.raises(DatabaseError):
        with sf.begin() as session:
            session.execute(text("DELETE FROM evidence WHERE id=:id"), {"id": evidence_id})
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("UPDATE evidence SET direction='INVALID' WHERE id=:id"), {"id": evidence_id})
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("INSERT INTO evidence (id,claim_document_link_id,direction,status,created_at,updated_at) VALUES ('duplicate',:link,'NEUTRAL','active','x','x')"), {"link": link_id})


def test_migration_from_stage6_backup_restore(tmp_path):
    settings = Settings(tmp_path / "store")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0006_candidates_claims")
    migration_backup = migrate(settings)
    assert migration_backup is not None and verify_backup(migration_backup)["format"] == 1
    sf = session_factory(settings)
    link_id = _linked(settings, sf)[0]
    with sf.begin() as session:
        record_evidence(session, link_id, "NEUTRAL", "TEST ONLY")
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("candidates", "claims", "claim_document_links", "evidence", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
