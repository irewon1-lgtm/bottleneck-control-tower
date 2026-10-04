import json

from alembic import command
from sqlalchemy import func, select

from bct.collectors.federal_register.collector import FederalRegisterCollector
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.models import AuditLog, CollectorRun, FederalRegisterDocument, RawDocument


def response(*, changed=False):
    return json.dumps({"description": "Documents matching semiconductor", "count": 3,
        "total_pages": 1, "results": [{
            "document_number": f"2026-1900{i}",
            "title": f"Semiconductor Policy {i}" + (" Revised" if changed else ""),
            "type": "Notice" if i != 2 else "Rule",
            "publication_date": f"2026-09-2{i}",
            "html_url": f"https://www.federalregister.gov/documents/2026/09/2{i}/2026-1900{i}/example",
            "agencies": [{"name": "Commerce Department"}]
        } for i in range(1, 4)]}).encode()


class FakeFR:
    def __init__(self, payload=None):
        self.payload = payload if payload is not None else response()
        self.requests = []

    def get(self, url):
        self.requests.append(url)
        return self.payload


def counts(sf):
    with sf() as db:
        return (db.scalar(select(func.count()).select_from(FederalRegisterDocument)),
                db.scalar(select(func.count()).select_from(RawDocument)))


def test_normal_collection_raw_and_metadata(setup):
    settings, sf = setup
    fake = FakeFR()
    result = FederalRegisterCollector(settings, fake).run("semiconductor", "normal")
    assert result.status == "succeeded" and result.saved == 3 and result.failed == 0
    assert counts(sf) == (3, 1) and len(list(settings.raw_dir.glob("*/*"))) == 1
    with sf() as db:
        for doc in db.scalars(select(FederalRegisterDocument)):
            raw = db.get(RawDocument, doc.raw_document_id)
            assert (settings.root / "raw" / raw.relative_path).read_bytes() == fake.payload
            assert doc.document_type in {"Notice", "Rule"}


def test_same_search_three_runs_no_duplicates(setup):
    settings, sf = setup
    fake = FakeFR()
    results = [FederalRegisterCollector(settings, fake).run("semiconductor", f"pass-{i}")
               for i in range(3)]
    assert [(r.saved, r.duplicates, r.updated) for r in results] == [
        (3, 0, 0), (0, 3, 0), (0, 3, 0)]
    assert counts(sf) == (3, 1)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(CollectorRun).where(
            CollectorRun.collector == "federal_register")) == 3


def test_bad_response_keeps_old_data_and_records_failure(setup):
    settings, sf = setup
    assert FederalRegisterCollector(settings, FakeFR()).run("semiconductor", "baseline").saved == 3
    broken = FederalRegisterCollector(settings, FakeFR(b'{"results":"wrong"}')).run(
        "semiconductor", "broken")
    assert broken.status == "failed" and broken.failed == 1 and "MalformedRecord" in broken.error
    assert counts(sf) == (3, 1)
    with sf() as db:
        run = db.get(CollectorRun, broken.run_id)
        assert run.status == "failed" and run.last_error


def test_partial_failure_then_same_key_retry(setup):
    settings, sf = setup
    collector = FederalRegisterCollector(settings, FakeFR())
    save = collector._save_document
    state = {"calls": 0}

    def fail_second(session, item, raw_id):
        state["calls"] += 1
        if state["calls"] == 2:
            raise IOError("simulated interrupted write")
        return save(session, item, raw_id)

    collector._save_document = fail_second
    first = collector.run("semiconductor", "retry")
    assert first.status == "failed" and first.saved == 1 and counts(sf) == (1, 1)
    second = FederalRegisterCollector(settings, FakeFR()).run("semiconductor", "retry")
    assert (second.saved, second.duplicates, second.failed) == (2, 1, 0)
    assert counts(sf) == (3, 1)
    with sf() as db:
        run = db.get(CollectorRun, first.run_id)
        assert run.attempts == 2 and run.status == "succeeded"


def test_updated_metadata_preserves_prior_raw_with_audit(setup):
    settings, sf = setup
    assert FederalRegisterCollector(settings, FakeFR()).run("semiconductor", "first").saved == 3
    updated = FederalRegisterCollector(settings, FakeFR(response(changed=True))).run(
        "semiconductor", "second")
    assert (updated.saved, updated.updated, updated.duplicates) == (0, 3, 0)
    assert counts(sf) == (3, 2)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "fr_document.updated")) == 3


def test_common_collect_contract_and_keyword_validation(setup):
    import pytest
    settings, sf = setup
    fake = FakeFR()
    records = list(FederalRegisterCollector(settings, fake).collect("critical minerals"))
    assert len(records) == 1 and records[0].content == fake.payload
    assert "critical+minerals" in fake.requests[0]
    assert counts(sf) == (0, 0)
    with pytest.raises(ValueError):
        list(FederalRegisterCollector(settings, fake).collect(""))


def test_stage2_to_stage3_migration_backs_up_old_db(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0003_contract_awards")
    backup = migrate(settings)
    assert backup is not None and (backup / "canonical.sqlite3").is_file()
    assert counts(session_factory(settings)) == (0, 0)
