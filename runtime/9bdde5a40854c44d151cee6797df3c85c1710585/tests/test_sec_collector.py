import json
from pathlib import Path

from alembic import command
from sqlalchemy import func, select

from bct.collectors.sec.collector import SECCollector, SECTransport
from bct.config import Settings
from bct.db import alembic_config, migrate, session_factory
from bct.models import CollectorRun, Document, RawDocument

CIK = "0000320193"
FORMS = ("10-K", "10-Q", "8-K")
ACCESSIONS = ("0000320193-26-000001", "0000320193-26-000002", "0000320193-26-000003")


def listing():
    return json.dumps({"cik": CIK, "filings": {"recent": {
        "form": list(FORMS), "accessionNumber": list(ACCESSIONS),
        "filingDate": ["2026-09-01", "2026-09-02", "2026-09-03"],
        "primaryDocument": ["report.htm", "quarter.htm", "event.htm"]}}}).encode()


class FakeSEC:
    def __init__(self, *, fail_document=None, malformed=False):
        self.fail_document = fail_document
        self.malformed = malformed
        self.requests = []

    def get(self, url):
        self.requests.append(url)
        if "/submissions/" in url:
            return b"{invalid" if self.malformed else listing()
        if self.fail_document and self.fail_document in url:
            raise IOError("simulated connection loss")
        return b"<html><body>" + url.encode() + b" SEC public filing text " * 50 + b"</body></html>"


def counts(sf):
    with sf() as s:
        return (s.scalar(select(func.count()).select_from(Document)),
                s.scalar(select(func.count()).select_from(RawDocument)))


def test_normal_collect_all_three_forms(setup):
    settings, sf = setup
    response = SECCollector(settings, FakeSEC()).run("320193", "normal")
    assert response.status == "succeeded" and response.saved == 3 and response.failed == 0
    assert counts(sf) == (3, 4)  # One original listing plus three original filing files.
    assert len(list(settings.raw_dir.glob("*/*"))) == 4
    with sf() as s:
        assert {d.form for d in s.scalars(select(Document))} == set(FORMS)
        for d in s.scalars(select(Document)):
            raw = s.get(RawDocument, d.raw_document_id)
            assert (settings.root / "raw" / raw.relative_path).read_bytes().startswith(b"<html>")


def test_common_collector_contract_yields_original_responses(setup):
    settings, sf = setup
    records = list(SECCollector(settings, FakeSEC()).collect(CIK))
    assert len(records) == 4
    assert {r.external_id for r in records[1:]} == set(ACCESSIONS)
    assert counts(sf) == (0, 0)  # Contract iteration alone does not persist.


def test_three_runs_deduplicate_same_filings(setup):
    settings, sf = setup
    fake = FakeSEC()
    results = [SECCollector(settings, fake).run(CIK, f"pass-{i}") for i in range(3)]
    assert [(r.saved, r.duplicates) for r in results] == [(3, 0), (0, 3), (0, 3)]
    assert counts(sf) == (3, 4)
    assert len(fake.requests) == 6  # 3 listings; filing content downloaded only once.
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(CollectorRun)) == 3


def test_malformed_response_preserves_previous_data_and_records_failure(setup):
    settings, sf = setup
    assert SECCollector(settings, FakeSEC()).run(CIK, "baseline").saved == 3
    result = SECCollector(settings, FakeSEC(malformed=True)).run(CIK, "broken")
    assert result.status == "failed" and result.failed == 1 and "MalformedRecord" in result.error
    assert counts(sf) == (3, 4)
    with sf() as s:
        run = s.get(CollectorRun, result.run_id)
        assert run.status == "failed" and run.last_error


def test_interrupted_run_resumes_without_redownloading_saved_document(setup):
    settings, sf = setup
    first = SECCollector(settings, FakeSEC(fail_document="quarter.htm")).run(CIK, "retry")
    assert first.status == "failed" and first.saved == 1 and counts(sf) == (1, 2)
    second_fetch = FakeSEC()
    second = SECCollector(settings, second_fetch).run(CIK, "retry")
    assert second.status == "succeeded" and second.saved == 2 and second.duplicates == 1
    assert len(second_fetch.requests) == 3  # Listing and two missing filing files.
    assert counts(sf) == (3, 4)
    with sf() as s:
        run = s.get(CollectorRun, first.run_id)
        assert run.attempts == 2 and run.status == "succeeded"


def test_recover_running_state_after_process_crash(setup):
    from bct.core import get_or_create_run, transition_run
    settings, sf = setup
    with sf.begin() as s:
        transition_run(s, get_or_create_run(s, "sec", f"{CIK}:crashed"), "running")
    result = SECCollector(settings, FakeSEC()).run(CIK, "crashed")
    assert result.status == "succeeded" and result.saved == 3
    with sf() as s:
        assert s.get(CollectorRun, result.run_id).attempts == 2


def test_upgrade_stage0_to_stage1_creates_pre_migration_backup(tmp_path):
    settings = Settings(tmp_path / "old")
    migrate(settings)
    command.downgrade(alembic_config(settings), "0001_foundation")
    backup = migrate(settings)
    assert backup is not None
    assert (backup / "canonical.sqlite3").exists()
    assert counts(session_factory(settings)) == (0, 0)


def test_transport_requires_identity_and_rejects_other_hosts():
    import pytest
    with pytest.raises(ValueError):
        SECTransport("")
    client = SECTransport("BCT research contact@example.org")
    with pytest.raises(ValueError):
        client.get("https://other.example/filing")
