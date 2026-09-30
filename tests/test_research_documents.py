import sqlite3
import uuid

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from bct.actors import link_document as actor_link, put_actor
from bct.backup import create_backup, restore_backup, verify_backup
from bct.candidates import link_document as claim_link, put_candidate, put_claim
from bct.collector import SourceRecord
from bct.config import Settings
from bct.core import ingest
from bct.db import alembic_config, migrate, session_factory
from bct.evidence import record_evidence
from bct.health import health
from bct.lineages import link_document as lineage_link, put_lineage
from bct.models import AuditLog, ClaimDocumentLink, Document, ResearchDocument
from bct.research import put_research_document, set_deleted


def test_research_original_links_dedupe_and_soft_delete(setup):
    settings, sf = setup
    url = "https://example.org/official-release"
    with sf.begin() as s:
        doc = put_research_document(settings, s, url, "Public release", "Publisher", b"<html>public</html>")
        assert put_research_document(settings, s, url, "Public release", "Publisher", b"<html>public</html>").id == doc.id
        candidate = put_candidate(s, "pilot:srm", "SRM")
        claim = put_claim(s, candidate.id, "Demand is increasing")
        link = claim_link(s, claim.id, "research", doc.id)
        assert claim_link(s, claim.id, "research", doc.id).id == link.id
        assert record_evidence(s, link.id, "SUPPORT", "direct statement").direction == "SUPPORT"
        lineage = put_lineage(s, "pilot:publisher", "Publisher release")
        actor = put_actor(s, "pilot:publisher", "Publisher", "COMPANY")
        assert lineage_link(s, lineage.id, "research", doc.id).id == lineage_link(s, lineage.id, "research", doc.id).id
        assert actor_link(s, actor.id, "research", doc.id).id == actor_link(s, actor.id, "research", doc.id).id
        set_deleted(s, doc, True)
        with pytest.raises(ValueError):
            record_evidence(s, link.id, "NEUTRAL")
        set_deleted(s, doc, False)
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(ResearchDocument)) == 1
        assert s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.event == "research_document.created")) == 1
        assert s.scalar(select(ClaimDocumentLink.research_document_id)) == doc.id
    with pytest.raises(IntegrityError):
        with sf.begin() as s:
            s.execute(text("DELETE FROM research_documents WHERE id=:id"), {"id": doc.id})
    assert health(settings, deep=True)["ok"]
    backup = create_backup(settings)
    assert verify_backup(backup)["files"]["canonical.sqlite3"]
    assert health(Settings(restore_backup(backup, settings.root.parent / "restored")), deep=True)["ok"]


def test_upgrade_preserves_existing_link_and_rejects_multiple_references(tmp_path):
    settings = Settings(tmp_path / "old")
    settings.mkdirs()
    command.upgrade(alembic_config(settings), "0011_claim_role")
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO candidates(id,stable_key,display_name,is_test,status,created_at,updated_at) VALUES('c','old','old',0,'active','x','x')")
        conn.execute("INSERT INTO claims(id,candidate_id,statement,role,status,created_at,updated_at) VALUES('q','c','old','OTHER','active','x','x')")
    with session_factory(settings).begin() as session:
        raw = ingest(settings, session, "sec", SourceRecord("old-filing", b"filing"))
        document = Document(source="sec", external_id="old-filing", cik="0000000001", form="8-K",
                            filing_date="2026-01-01", source_url="https://example.org/old", raw_document_id=raw.id)
        session.add(document)
        session.flush()
        old_document_id = document.id
    old_link_id = str(uuid.uuid4())
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO claim_document_links(id,claim_id,sec_document_id,status,created_at,updated_at) VALUES(?,?,?,'active','x','x')",
                     (old_link_id, "q", old_document_id))
    prebackup = migrate(settings)
    assert prebackup is not None
    with sqlite3.connect(settings.db_path) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT statement FROM claims WHERE id='q'").fetchone()[0] == "old"
        assert conn.execute("SELECT id FROM claim_document_links WHERE id=? AND research_document_id IS NULL", (old_link_id,)).fetchone()[0] == old_link_id
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
    with session_factory(settings).begin() as session:
        research = put_research_document(settings, session, "https://example.org/new", "New", "Publisher", b"<html>new</html>")
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(text("UPDATE claim_document_links SET research_document_id=:doc WHERE id=:link"),
                                {"doc": research.id, "link": old_link_id})
    assert health(settings, deep=True)["ok"]
