import sqlite3

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from bct.backup import create_backup, restore_backup, verify_backup
from bct.candidates import link_document, put_candidate, put_claim, set_deleted
from bct.collector import SourceRecord
from bct.config import Settings
from bct.core import ingest
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.models import (AuditLog, Candidate, Claim, ClaimDocumentLink, ContractAward,
                        Document, FederalRegisterDocument)


def _documents(settings, sf):
    with sf.begin() as session:
        raw = ingest(settings, session, "test", SourceRecord("seed", b"test source response"))
        sec = Document(source="sec", external_id="a1", cik="1", form="10-K",
                       filing_date="2026-09-29", source_url="https://www.sec.gov/1",
                       raw_document_id=raw.id)
        award = ContractAward(source="usaspending", external_id="a2", award_id="A2",
                              recipient_name="Test", raw_document_id=raw.id)
        fr = FederalRegisterDocument(source="federal_register", external_id="2026-10001",
             title="Test notice", document_type="Notice", publication_date="2026-09-29",
             html_url="https://www.federalregister.gov/documents/test", raw_document_id=raw.id)
        session.add_all((sec, award, fr))
        session.flush()
        return sec.id, award.id, fr.id


def test_one_test_candidate_three_claims_and_each_document_type(setup):
    settings, sf = setup
    ids = _documents(settings, sf)
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        claims = [put_claim(session, candidate.id, f"TEST ONLY: unverified hypothesis {i}")
                  for i in range(3)]
        links = [link_document(session, claim.id, source, doc_id)
                 for claim, source, doc_id in zip(claims, ("sec", "usaspending", "federal_register"), ids)]
        assert put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True).id == candidate.id
        assert put_claim(session, candidate.id, claims[0].statement).id == claims[0].id
        assert link_document(session, claims[0].id, "sec", ids[0]).id == links[0].id
    with sf() as session:
        assert session.scalar(select(func.count()).select_from(Candidate)) == 1
        assert session.scalar(select(func.count()).select_from(Claim)) == 3
        assert session.scalar(select(func.count()).select_from(ClaimDocumentLink)) == 3
        assert session.get(Candidate, candidate.id).is_test is True
        assert [r.statement for r in session.scalars(select(Claim).where(
            Claim.candidate_id == candidate.id).order_by(Claim.statement))] == [
                f"TEST ONLY: unverified hypothesis {i}" for i in range(3)]
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "claim_document.linked")) == 3


def test_soft_delete_restore_guards_and_invalid_reference(setup):
    settings, sf = setup
    sec_id, _, _ = _documents(settings, sf)
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        claim = put_claim(session, candidate.id, "TEST ONLY: unverified")
        link = link_document(session, claim.id, "sec", sec_id)
        cid, claim_id, link_id = candidate.id, claim.id, link.id
        for item in (link, claim, candidate):
            set_deleted(session, item, True)
        with pytest.raises(ValueError):
            put_claim(session, cid, "another")
        for item in (candidate, claim, link):
            set_deleted(session, item, False)
        assert link_document(session, claim_id, "sec", sec_id).id == link_id
        with pytest.raises(ValueError):
            link_document(session, claim_id, "sec", "missing")
    with sf() as session:
        assert session.get(ClaimDocumentLink, link_id).deleted_at is None
        assert session.get(Claim, claim_id).status == "active"
        assert session.get(Candidate, cid).status == "active"
        assert session.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event.in_(["candidate.deleted", "candidate.restored",
                                  "claim.deleted", "claim.restored",
                                  "claim_document_link.deleted", "claim_document_link.restored"]))) == 6
    for table in ("claim_document_links", "claims", "candidates"):
        with pytest.raises(DatabaseError):
            with sf.begin() as session:
                session.execute(text(f"DELETE FROM {table}"))
    with pytest.raises(IntegrityError):
        with sf.begin() as session:
            session.execute(text("INSERT INTO claim_document_links (id,claim_id,sec_document_id,contract_award_id,status,created_at,updated_at) VALUES ('wrong',:claim,:sec,:award,'active','x','x')"),
                            {"claim": claim_id, "sec": sec_id, "award": "missing"})


def test_migration_and_backup_restore_candidate_claim_links(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0005_federal_register_full_texts")
    migration_backup = migrate(settings)
    assert migration_backup is not None and verify_backup(migration_backup)["format"] == 1
    sf = session_factory(settings)
    sec_id, _, _ = _documents(settings, sf)
    with sf.begin() as session:
        candidate = put_candidate(session, "test:srm", "TEST ONLY: SRM", is_test=True)
        claim = put_claim(session, candidate.id, "TEST ONLY: unverified")
        link_document(session, claim.id, "sec", sec_id)
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert health(Settings(restored), deep=True)["ok"]
    with sqlite3.connect(settings.db_path) as live, sqlite3.connect(restored / "canonical/canonical.sqlite3") as copy:
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        for table in ("candidates", "claims", "claim_document_links", "audit_log"):
            assert live.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == copy.execute(
                f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    for name, digest in manifest["files"].items():
        file = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        import hashlib
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest
