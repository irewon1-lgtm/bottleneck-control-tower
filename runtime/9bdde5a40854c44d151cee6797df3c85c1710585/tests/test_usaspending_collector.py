import json
from pathlib import Path

from alembic import command
from sqlalchemy import func, select

from bct.collectors.usaspending.collector import (USAspendingCollector, request_body,
                                                    parse_response)
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.models import AuditLog, CollectorRun, ContractAward, RawDocument


def response(*, amount=1000.0):
    return json.dumps({"spending_level": "awards", "limit": 3, "results": [
        {"generated_internal_id": f"CONT_AWD_{i}_agency", "Award ID": f"PIID-{i}",
         "Recipient Name": "SAMPLE DEFENSE CORP", "Award Amount": amount + i,
         "Awarding Agency": "Department of Defense", "Last Modified Date": "2026-09-25 10:00:00"}
        for i in range(1, 4)]}).encode()


class FakeUSA:
    def __init__(self, payload=None):
        self.payload = payload if payload is not None else response()
        self.requests = []

    def post(self, body):
        self.requests.append(body)
        return self.payload


def counts(sf):
    with sf() as db:
        return (db.scalar(select(func.count()).select_from(ContractAward)),
                db.scalar(select(func.count()).select_from(RawDocument)))


def test_normal_contract_collection_and_raw_provenance(setup):
    settings, sf = setup
    fake = FakeUSA()
    result = USAspendingCollector(settings, fake).run("SAMPLE DEFENSE", "normal")
    assert result.status == "succeeded" and result.saved == 3 and result.failed == 0
    assert counts(sf) == (3, 1)
    assert len(list(settings.raw_dir.glob("*/*"))) == 1
    assert fake.requests[0]["filters"]["award_type_codes"] == ["A", "B", "C", "D"]
    with sf() as db:
        for award in db.scalars(select(ContractAward)):
            raw = db.get(RawDocument, award.raw_document_id)
            assert (settings.root / "raw" / raw.relative_path).read_bytes() == fake.payload


def test_same_request_three_runs_no_duplicate(setup):
    settings, sf = setup
    fake = FakeUSA()
    results = [USAspendingCollector(settings, fake).run("SAMPLE DEFENSE", f"pass-{i}")
               for i in range(3)]
    assert [(x.saved, x.duplicates, x.updated) for x in results] == [
        (3, 0, 0), (0, 3, 0), (0, 3, 0)]
    assert counts(sf) == (3, 1)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(CollectorRun).where(
            CollectorRun.collector == "usaspending")) == 3


def test_malformed_response_preserves_existing_data_and_records_failure(setup):
    settings, sf = setup
    assert USAspendingCollector(settings, FakeUSA()).run("SAMPLE DEFENSE", "baseline").saved == 3
    result = USAspendingCollector(settings, FakeUSA(b'{"results":"wrong"}')).run(
        "SAMPLE DEFENSE", "malformed")
    assert result.status == "failed" and result.failed == 1 and "MalformedRecord" in result.error
    assert counts(sf) == (3, 1)
    with sf() as db:
        run = db.get(CollectorRun, result.run_id)
        assert run.status == "failed" and run.last_error


def test_partial_failure_same_key_retry(setup):
    settings, sf = setup
    collector = USAspendingCollector(settings, FakeUSA())
    original = collector._save_award
    state = {"calls": 0}

    def fail_on_second(session, award, raw_id):
        state["calls"] += 1
        if state["calls"] == 2:
            raise IOError("temporary database write failure")
        return original(session, award, raw_id)

    collector._save_award = fail_on_second
    first = collector.run("SAMPLE DEFENSE", "retry")
    assert first.status == "failed" and first.saved == 1 and counts(sf) == (1, 1)
    second = USAspendingCollector(settings, FakeUSA()).run("SAMPLE DEFENSE", "retry")
    assert second.status == "succeeded" and second.saved == 2 and second.duplicates == 1
    assert counts(sf) == (3, 1)
    with sf() as db:
        run = db.get(CollectorRun, first.run_id)
        assert run.attempts == 2 and run.status == "succeeded"


def test_changed_contract_metadata_updates_with_audit_and_raw_history(setup):
    settings, sf = setup
    assert USAspendingCollector(settings, FakeUSA()).run("SAMPLE DEFENSE", "old").saved == 3
    result = USAspendingCollector(settings, FakeUSA(response(amount=2000))).run("SAMPLE DEFENSE", "new")
    assert (result.saved, result.updated, result.duplicates) == (0, 3, 0)
    assert counts(sf) == (3, 2)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "contract_award.updated")) == 3


def test_keyword_mode_and_common_contract(setup):
    settings, sf = setup
    fake = FakeUSA()
    records = list(USAspendingCollector(settings, fake).collect("keyword:semiconductor"))
    assert len(records) == 1 and records[0].content == fake.payload
    assert fake.requests[0]["filters"]["keywords"] == ["semiconductor"]
    result = USAspendingCollector(settings, fake).run("semiconductor", "keyword", mode="keyword")
    assert result.saved == 3 and counts(sf) == (3, 1)


def test_stage1_to_stage2_migration_makes_backup(tmp_path):
    settings = Settings(tmp_path / "prestage2")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0002_documents")
    backup = migrate(settings)
    assert backup is not None and (backup / "canonical.sqlite3").is_file()
    assert counts(session_factory(settings)) == (0, 0)
