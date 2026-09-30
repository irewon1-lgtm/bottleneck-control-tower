import json
from datetime import date

from sqlalchemy import func, select

from bct.backup import create_backup, restore_backup, verify_backup
from bct.collectors.media_cloud.cli import main
from bct.collectors.media_cloud.collector import MediaCloudCollector, MediaCloudTransport, QUERIES
from bct.config import Settings
from bct.db import session_factory
from bct.models import AuditLog, CollectorRun, RadarItem


def response(changed=False):
    return json.dumps({"stories": [{
        "id": f"{n:064x}", "media_url": "example.org", "publish_date": "2026-09-29",
        "title": f"Industry shortage {n}" + (" revised" if changed and n == 1 else ""),
        "url": f"https://example.org/news/{n}"} for n in range(1, 4)],
        "pagination_token": None}).encode()


class FakeTransport:
    api_key = "test-only"

    def __init__(self, payload=None):
        self.payload = response() if payload is None else payload

    def get(self, url):
        assert "page_size=5" in url and "cs=34412234" in url
        return self.payload


def counts(sf):
    with sf() as db:
        return db.scalar(select(func.count()).select_from(RadarItem))


def test_collection_repeat_three_times_update_and_backup(setup, tmp_path):
    settings, sf = setup
    collector = MediaCloudCollector(settings, FakeTransport())
    runs = [collector.run("shortage", f"repeat-{i}", day=date(2026, 9, 29))
            for i in range(3)]
    assert [(r.saved, r.duplicates, r.failed) for r in runs] == [
        (3, 0, 0), (0, 3, 0), (0, 3, 0)]
    assert counts(sf) == 3
    changed = MediaCloudCollector(settings, FakeTransport(response(changed=True))).run(
        "shortage", "changed", day=date(2026, 9, 29))
    assert (changed.saved, changed.updated, changed.duplicates) == (0, 1, 2)
    with sf() as db:
        row = db.scalar(select(RadarItem).where(RadarItem.external_id == f"{1:064x}"))
        assert row.published_at == "2026-09-29" and row.snippet is None
        event = db.scalar(select(AuditLog).where(AuditLog.event == "radar.updated"))
        assert json.loads(event.details_json)["changes"]["title"]["old"] == "Industry shortage 1"
    backup = create_backup(settings)
    assert verify_backup(backup)
    other = session_factory(Settings(restore_backup(backup, tmp_path / "restored")))
    assert counts(other) == 3


def test_bad_response_preserves_rows_and_same_key_can_retry(setup):
    settings, sf = setup
    assert MediaCloudCollector(settings, FakeTransport()).run("shortage", "initial").saved == 3
    malformed = json.dumps({"stories": [
        {"id": f"{4:064x}", "title": "Valid", "url": "https://example.org/new"},
        {"id": "bad", "title": "Invalid", "url": "https://example.org/bad"}]}).encode()
    failure = MediaCloudCollector(settings, FakeTransport(malformed)).run("shortage", "retry")
    assert failure.status == "failed" and failure.failed == 1 and counts(sf) == 3
    success = MediaCloudCollector(settings, FakeTransport()).run("shortage", "retry")
    assert (success.saved, success.duplicates, success.failed) == (0, 3, 0)
    with sf() as db:
        run = db.get(CollectorRun, failure.run_id)
        assert run.attempts == 2 and run.status == "succeeded"


def test_timeout_one_query_does_not_block_second_in_cli(setup, tmp_path, monkeypatch, capsys):
    settings, sf = setup
    config = tmp_path / "config.yaml"
    config.write_text(f"storage_root: {settings.root}\n")

    class OneTimeout(FakeTransport):
        def get(self, url):
            if "q=shortage" in url:
                raise TimeoutError("simulated timeout")
            return super().get(url)

    monkeypatch.setattr("bct.collectors.media_cloud.cli.MediaCloudTransport", OneTimeout)
    monkeypatch.setattr("bct.collectors.media_cloud.cli.time.sleep", lambda _: None)
    argv = ["--config", str(config), "--run-key", "first", "--limit", "5",
            "--query", "shortage", "--query", '"lead time"']
    assert main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert [(r["status"], r["saved"]) for r in first] == [("failed", 0), ("succeeded", 3)]
    assert main(argv[:3] + ["second"] + argv[4:]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second[1]["duplicates"] == 3 and counts(sf) == 3
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(CollectorRun).where(
            CollectorRun.collector == "radar_media_cloud")) == 4


def test_missing_api_key_is_a_recorded_failure(setup, monkeypatch):
    settings, sf = setup
    monkeypatch.delenv("MEDIACLOUD_API_KEY", raising=False)
    result = MediaCloudCollector(settings, MediaCloudTransport()).run("shortage", "no-key")
    assert result.status == "failed" and "MEDIACLOUD_API_KEY" in result.error
    assert counts(sf) == 0
    assert len(QUERIES) == 3
