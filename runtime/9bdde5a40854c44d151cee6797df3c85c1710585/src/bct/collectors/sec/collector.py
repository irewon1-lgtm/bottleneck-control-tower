import json
import re
import time
from dataclasses import dataclass
from datetime import date
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import Collector, MalformedRecord, SourceRecord, RunResult, execute_run
from bct.config import Settings
from bct.core import audit, ingest
from bct.db import session_factory
from bct.models import Document

FORMS = ("10-K", "10-Q", "8-K")
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


@dataclass(frozen=True)
class Filing:
    cik: str
    accession: str
    form: str
    filing_date: str
    url: str


class SECTransport:
    """One serial requester, explicit identity, hard limits, no automatic retries."""

    def __init__(self, user_agent: str, *, interval_seconds: float = 0.25,
                 timeout_seconds: int = 25, max_bytes: int = 20_000_000):
        if not isinstance(user_agent, str) or len(user_agent.strip()) < 12:
            raise ValueError("identify the project and contact in the SEC User-Agent")
        if interval_seconds < 0.1 or timeout_seconds <= 0 or max_bytes < 1024:
            raise ValueError("invalid transport limits")
        self.user_agent = user_agent
        self.interval = interval_seconds
        self.timeout = timeout_seconds
        self.max_bytes = max_bytes
        self._previous = None

    def get(self, url: str) -> bytes:
        if not (url.startswith("https://data.sec.gov/submissions/CIK") or
                url.startswith("https://www.sec.gov/Archives/edgar/data/")):
            raise ValueError("unapproved SEC URL")
        if self._previous is not None:
            wait = self.interval - (time.monotonic() - self._previous)
            if wait > 0:
                time.sleep(wait)
        self._previous = time.monotonic()
        request = Request(url, headers={"User-Agent": self.user_agent,
                                        "Accept-Encoding": "identity", "Accept": "*/*"})
        with urlopen(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise IOError(f"SEC HTTP {response.status}")
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise IOError("SEC response exceeded max_bytes")
        return data


def parse_listing(payload: bytes, cik: str, max_per_form: int) -> list[Filing]:
    try:
        listing = json.loads(payload)
        if str(listing["cik"]).zfill(10) != cik:
            raise ValueError("CIK mismatch")
        recent = listing["filings"]["recent"]
        columns = {k: recent[k] for k in ("form", "accessionNumber", "filingDate", "primaryDocument")}
        if not all(isinstance(v, list) for v in columns.values()) or len({len(v) for v in columns.values()}) != 1:
            raise ValueError("invalid recent arrays")
        counts = {form: 0 for form in FORMS}
        result = []
        for form, accession, filing_date, filename in zip(*columns.values()):
            if form not in counts or counts[form] >= max_per_form:
                continue
            if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                raise ValueError("invalid accession")
            date.fromisoformat(filing_date)
            if not isinstance(filename, str) or not FILENAME.fullmatch(filename) or ".." in filename:
                raise ValueError("invalid primary document filename")
            url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                   f"{accession.replace('-', '')}/{filename}")
            result.append(Filing(cik, accession, form, filing_date, url))
            counts[form] += 1
        return result
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise MalformedRecord(f"invalid SEC submissions response: {exc}") from exc


def validate_filing(payload: bytes) -> None:
    # Stage 1 deliberately selects the main HTML document, not every exhibit.
    if not isinstance(payload, bytes) or len(payload) < 200 or b"<html" not in payload[:50000].lower():
        raise MalformedRecord("invalid SEC primary filing response")


class SECCollector(Collector):
    name = "sec"

    def __init__(self, settings: Settings, transport: SECTransport):
        self.settings = settings
        self.transport = transport
        self.sf = session_factory(settings)

    def collect(self, checkpoint: str | None = None):
        """Read-only common adapter contract; run() provides persistence and skips duplicates."""
        if checkpoint is None:
            raise ValueError("SEC collector checkpoint must be a CIK")
        cik = normalize_cik(checkpoint)
        payload = self.transport.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
        filings = parse_listing(payload, cik, 1)
        yield SourceRecord(external_id=cik, content=payload, media_type="application/json")
        for filing in filings:
            data = self.transport.get(filing.url)
            validate_filing(data)
            yield SourceRecord(external_id=filing.accession, content=data, media_type="text/html")

    def run(self, cik: str, run_key: str, *, max_per_form: int = 1) -> RunResult:
        cik = normalize_cik(cik)
        if type(max_per_form) is not int or not 1 <= max_per_form <= 100:
            raise ValueError("max_per_form must be 1..100")
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        def work(progress):
            payload = self.transport.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            filings = parse_listing(payload, cik, max_per_form)
            with self.sf.begin() as session:
                ingest(self.settings, session, "sec.submissions",
                       SourceRecord(cik, payload, "application/json"))
            for filing in filings:
                with self.sf() as session:
                    exists = session.scalar(select(Document.id).where(Document.source == "sec",
                                                                     Document.external_id == filing.accession))
                if exists:
                    progress.duplicates += 1
                    continue
                document_bytes = self.transport.get(filing.url)
                validate_filing(document_bytes)
                with self.sf.begin() as session:
                    # Check again within the write transaction before inserting.
                    exists = session.scalar(select(Document.id).where(Document.source == "sec",
                                                                         Document.external_id == filing.accession))
                    if exists:
                        progress.duplicates += 1
                        continue
                    raw = ingest(self.settings, session, "sec.filing",
                                 SourceRecord(filing.accession, document_bytes, "text/html"))
                    doc = Document(source="sec", external_id=filing.accession, cik=filing.cik,
                                   form=filing.form, filing_date=filing.filing_date,
                                   source_url=filing.url, raw_document_id=raw.id)
                    session.add(doc)
                    session.flush()
                    audit(session, "document.created", "document", doc.id,
                          {"accession": filing.accession, "form": filing.form,
                           "raw_document_id": raw.id})
                progress.saved += 1
        return execute_run(self.sf, self.name, f"{cik}:{run_key}", work)


def normalize_cik(value: str) -> str:
    if not isinstance(value, str) or not value.isdigit() or not 1 <= len(value) <= 10 or int(value) < 1:
        raise ValueError("CIK must be 1..10 digits")
    return value.zfill(10)
