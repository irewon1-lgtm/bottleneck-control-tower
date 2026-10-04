import hashlib
import sqlite3

from alembic import command
from sqlalchemy import func, select

from bct.backup import create_backup, restore_backup, verify_backup
from bct.collectors.federal_register.collector import FederalRegisterCollector
from bct.collectors.federal_register.fulltext import fetch_full_text
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.health import health
from bct.models import AuditLog, CollectorRun, FederalRegisterFullText, RawDocument
from test_federal_register_collector import FakeFR


class FakeText:
    def __init__(self, payload=b"[FR Doc. 2026-19001 Filed 9-20-26]\n", error=None):
        self.payload, self.error, self.urls = payload, error, []

    def get(self, url):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.payload


def seeded(setup):
    settings, sf = setup
    assert FederalRegisterCollector(settings, FakeFR()).run("semiconductor", "seed").saved == 3
    return settings, sf


def test_save_link_repeated_download_and_audit(setup):
    settings, sf = seeded(setup)
    transport = FakeText()
    results = [fetch_full_text(settings, "2026-19001", f"pass-{i}", transport) for i in range(3)]
    assert [(r.saved, r.duplicates) for r in results] == [(1, 0), (0, 1), (0, 1)]
    assert len(transport.urls) == 3 and transport.urls[0].endswith("/2026/09/21/2026-19001.txt")
    with sf() as db:
        links = db.scalars(select(FederalRegisterFullText)).all()
        assert len(links) == 1
        raw = db.get(RawDocument, links[0].raw_document_id)
        assert raw.source == "federal_register.full_text"
        assert raw.sha256 == hashlib.sha256(transport.payload).hexdigest()
        assert (settings.root / "raw" / raw.relative_path).read_bytes() == transport.payload
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "fr_full_text.linked")) == 1
        assert db.scalar(select(func.count()).select_from(RawDocument)) == 2
    assert fetch_full_text(settings, "2026-19001", "pass-0", transport).saved == 0
    assert len(transport.urls) == 3  # A completed run is skipped.


def test_failed_download_and_bad_body_preserve_existing_data_then_retry(setup):
    settings, sf = seeded(setup)
    good = FakeText()
    assert fetch_full_text(settings, "2026-19001", "good", good).saved == 1
    initial = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in settings.raw_dir.glob("*/*")}
    bad = fetch_full_text(settings, "2026-19002", "retry", FakeText(error=IOError("timeout")))
    assert bad.status == "failed" and "timeout" in bad.error
    mismatch = fetch_full_text(settings, "2026-19003", "bad", FakeText(payload=b"wrong document"))
    assert mismatch.status == "failed" and "MalformedRecord" in mismatch.error
    assert initial == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in settings.raw_dir.glob("*/*")}
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(FederalRegisterFullText)) == 1
        assert db.scalar(select(func.count()).select_from(RawDocument)) == 2
        assert db.get(CollectorRun, bad.run_id).last_error
    recovered = fetch_full_text(settings, "2026-19002", "retry", FakeText(payload=b"[FR Doc. 2026-19002]\n"))
    assert recovered.status == "succeeded" and recovered.run_id == bad.run_id and recovered.saved == 1
    with sf() as db:
        assert db.get(CollectorRun, bad.run_id).attempts == 2


def test_changed_original_keeps_prior_version_and_backup_restore(setup, tmp_path):
    settings, sf = seeded(setup)
    assert fetch_full_text(settings, "2026-19001", "first", FakeText()).saved == 1
    assert fetch_full_text(settings, "2026-19001", "changed",
        FakeText(payload=b"[FR Doc. 2026-19001 amended bytes]\n")).saved == 1
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(FederalRegisterFullText)) == 2
    backup = create_backup(settings)
    manifest = verify_backup(backup)
    restored = restore_backup(backup, tmp_path / "restored")
    assert len(manifest["files"]) == 4  # One search response and two original versions.
    assert health(Settings(restored), deep=True)["ok"]
    for name, digest in manifest["files"].items():
        path = restored / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    with session_factory(Settings(restored))() as db:
        assert db.scalar(select(func.count()).select_from(FederalRegisterFullText)) == 2


def test_migration_from_stage4_creates_pre_migration_backup(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0004_federal_register_documents")
    backup = migrate(settings)
    assert backup is not None and verify_backup(backup)["format"] == 1
    with sqlite3.connect(settings.db_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013_radar_items"
        assert conn.execute("SELECT count(*) FROM federal_register_full_texts").fetchone()[0] == 0
