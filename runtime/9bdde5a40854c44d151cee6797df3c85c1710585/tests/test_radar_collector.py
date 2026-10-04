import json
import sqlite3

from alembic import command
from sqlalchemy import func, select

from bct.backup import create_backup, restore_backup, verify_backup
from bct.collectors.radar.collector import RadarCollector, QUERIES, feed_url
from bct.collectors.radar.cli import main
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.models import AuditLog, CollectorRun, RadarItem, RawDocument


def response(changed=False):
    return json.dumps({"articles": [
        {"url": "https://example.org/industry/a", "title": "Capacity expands" + (" today" if changed else "")},
        {"url": "https://other.org/manufacturing/b", "title": "Lead times"},
        {"url": "https://third.org/supply/c", "title": "Production delay"},
    ]}).encode()


class FakeTransport:
    def __init__(self, payload=None):
        self.payload = response() if payload is None else payload

    def get(self, url):
        assert "shortage" in url and "maxrecords=10" in url
        return self.payload


def count(sf):
    with sf() as db:
        return db.scalar(select(func.count()).select_from(RadarItem))


def test_repeated_three_times_and_metadata_update_are_audited(setup):
    settings, sf = setup
    collector = RadarCollector(settings, FakeTransport())
    results = [collector.run(f"pass-{n}") for n in range(3)]
    assert [(r.saved, r.duplicates, r.updated, r.failed) for r in results] == [
        (3, 0, 0, 0), (0, 3, 0, 0), (0, 3, 0, 0)]
    assert count(sf) == 3
    with sf() as db:
        prior = db.scalar(select(RadarItem).where(RadarItem.source == "example.org"))
        original_id, original_time = prior.id, prior.updated_at
    changed = RadarCollector(settings, FakeTransport(response(changed=True))).run("changed")
    assert (changed.saved, changed.updated, changed.duplicates) == (0, 1, 2)
    with sf() as db:
        row = db.get(RadarItem, original_id)
        event = db.scalar(select(AuditLog).where(AuditLog.event == "radar.updated"))
        assert row.id == original_id and row.title == "Capacity expands today"
        assert row.updated_at >= original_time
        assert json.loads(event.details_json)["changes"]["title"] == {
            "old": "Capacity expands", "new": "Capacity expands today"}
        assert db.scalar(select(func.count()).select_from(RawDocument)) == 0


def test_malformed_response_preserves_existing_data_and_retry(setup):
    settings, sf = setup
    assert RadarCollector(settings, FakeTransport()).run("baseline").saved == 3
    malformed = json.dumps({"articles": [
        {"title": "A", "url": "https://example.org/new"},
        {"title": "B", "url": "file:///invalid"}]}).encode()
    bad = RadarCollector(settings, FakeTransport(malformed)).run("retry")
    assert bad.failed == 1 and bad.status == "failed" and count(sf) == 3
    again = RadarCollector(settings, FakeTransport()).run("retry")
    assert (again.saved, again.duplicates, again.failed) == (0, 3, 0)
    with sf() as db:
        run = db.get(CollectorRun, bad.run_id)
        assert run.attempts == 2 and run.status == "succeeded"
        events = db.scalars(select(AuditLog).where(AuditLog.object_id == bad.run_id)).all()
        assert any(json.loads(e.details_json).get("error") for e in events)


def test_partial_transaction_failure_then_same_key_retry(setup):
    settings, sf = setup
    collector = RadarCollector(settings, FakeTransport())
    original = collector._save_item
    state = {"calls": 0}

    def failing(session, item):
        state["calls"] += 1
        outcome = original(session, item)
        if state["calls"] == 2:
            raise sqlite3.OperationalError("simulated commit failure")
        return outcome

    collector._save_item = failing
    first = collector.run("interrupted")
    assert first.status == "failed" and first.saved == 1 and count(sf) == 1
    second = RadarCollector(settings, FakeTransport()).run("interrupted")
    assert (second.saved, second.duplicates, second.failed, count(sf)) == (2, 1, 0, 3)


def test_backup_restore_and_soft_delete_not_resurrected(setup, tmp_path):
    settings, sf = setup
    assert RadarCollector(settings, FakeTransport()).run("original").saved == 3
    with sf.begin() as db:
        row = db.scalar(select(RadarItem).where(RadarItem.source == "example.org"))
        row.status, row.deleted_at = "deleted", "2026-09-29T00:00:00+00:00"
        from bct.core import audit
        audit(db, "radar.deleted", "radar_item", row.id, {"status": "deleted"})
    result = RadarCollector(settings, FakeTransport()).run("after-delete")
    assert result.duplicates == 3
    backup = create_backup(settings)
    assert verify_backup(backup)["files"]
    recovered = Settings(restore_backup(backup, tmp_path / "recovered"))
    other = session_factory(recovered)
    assert count(other) == 3
    with other() as db:
        row = db.scalar(select(RadarItem).where(RadarItem.source == "example.org"))
        assert row.status == "deleted" and row.deleted_at
        assert db.scalar(select(func.count()).select_from(AuditLog)) > 0


def test_migration_from_previous_head_creates_backup(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0012_research_documents")
    backup = migrate(settings)
    assert backup is not None and verify_backup(backup)
    assert count(session_factory(settings)) == 0


def test_small_queries_are_separate_runs_and_failed_query_does_not_block_others(setup, monkeypatch, tmp_path, capsys):
    settings, sf = setup
    config = tmp_path / "config.yaml"
    config.write_text(f"storage_root: {settings.root}\n")
    class OneTimeout:
        def get(self, url):
            if "query=shortage" in url:
                raise TimeoutError("simulated timeout")
            return response()

    monkeypatch.setattr("bct.collectors.radar.cli.GDELTTransport", OneTimeout)
    args = ["--config", str(config), "--run-key", "batch-1", "--limit", "10",
            "--query", "shortage", "--query", '"lead time"']
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert [(r["status"], r["saved"], r["failed"]) for r in first] == [
        ("failed", 0, 1), ("succeeded", 3, 0)]
    assert count(sf) == 3
    # A fresh key actually re-fetches. It cannot insert the same article twice.
    assert main(args[:3] + ["batch-2"] + args[4:]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second[1]["duplicates"] == 3 and count(sf) == 3
    with sf() as db:
        runs = db.scalars(select(CollectorRun).where(CollectorRun.collector == "radar_gdelt")).all()
        assert len(runs) == 4 and sum(r.status == "failed" for r in runs) == 2


def test_query_urls_are_small_and_distinct():
    urls = [feed_url(10, query) for query in QUERIES]
    assert len(set(urls)) == 5
    assert all("maxrecords=10" in url and "timespan=24h" in url for url in urls)
