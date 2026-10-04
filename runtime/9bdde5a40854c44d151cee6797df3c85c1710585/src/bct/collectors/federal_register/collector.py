import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import Collector, MalformedRecord, RunResult, SourceRecord, execute_run
from bct.config import Settings
from bct.core import audit, ingest
from bct.db import session_factory
from bct.models import FederalRegisterDocument, now

ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
DOCUMENT_NUMBER = re.compile(r"^[A-Za-z0-9-]{3,80}$")


@dataclass(frozen=True)
class SearchDocument:
    number: str
    title: str
    document_type: str
    publication_date: str
    agency_names: str | None
    html_url: str


def search_params(keyword: str, limit: int) -> dict[str, str | int]:
    if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 150:
        raise ValueError("keyword must be 1..150 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    return {"conditions[term]": keyword.strip(), "per_page": limit, "order": "newest"}


def search_url(params: dict[str, str | int]) -> str:
    return ENDPOINT + "?" + urlencode(sorted(params.items()))


def parse_response(payload: bytes, limit: int) -> list[SearchDocument]:
    try:
        data = json.loads(payload)
        rows = data["results"]
        if not isinstance(rows, list) or len(rows) > limit or type(data.get("count")) is not int or data["count"] < len(rows):
            raise ValueError("invalid search results")
        documents = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid result item")
            number, title, kind = row["document_number"], row["title"], row["type"]
            published, url = row["publication_date"], row["html_url"]
            if not isinstance(number, str) or not DOCUMENT_NUMBER.fullmatch(number):
                raise ValueError("invalid document_number")
            if not isinstance(title, str) or not title.strip() or len(title) > 2000:
                raise ValueError("invalid title")
            if not isinstance(kind, str) or not kind.strip() or len(kind) > 80:
                raise ValueError("invalid type")
            date.fromisoformat(published)
            if not isinstance(url, str) or not url.startswith("https://www.federalregister.gov/documents/") or len(url) > 1200:
                raise ValueError("invalid html_url")
            agencies = row.get("agencies")
            if agencies is not None and not isinstance(agencies, list):
                raise ValueError("invalid agencies")
            names = []
            for agency in agencies or []:
                if not isinstance(agency, dict) or not isinstance(agency.get("name"), str):
                    raise ValueError("invalid agency item")
                names.append(agency["name"])
            joined = ", ".join(names) or None
            if joined is not None and len(joined) > 1000:
                raise ValueError("agency list too long")
            documents.append(SearchDocument(number, title, kind, published, joined, url))
        return documents
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise MalformedRecord(f"invalid Federal Register response: {exc}") from exc


class FederalRegisterTransport:
    def __init__(self, *, timeout_seconds: int = 25, max_bytes: int = 4_000_000):
        if timeout_seconds <= 0 or max_bytes < 1024:
            raise ValueError("invalid transport limits")
        self.timeout = timeout_seconds
        self.max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if not url.startswith(ENDPOINT + "?"):
            raise ValueError("invalid Federal Register API URL")
        request = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "BottleneckControlTower/0.4"})
        with urlopen(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise IOError(f"Federal Register HTTP {response.status}")
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise IOError("Federal Register response exceeded max_bytes")
        return payload


class FederalRegisterCollector(Collector):
    name = "federal_register"

    def __init__(self, settings: Settings, transport: FederalRegisterTransport):
        self.settings = settings
        self.transport = transport
        self.sf = session_factory(settings)

    def collect(self, checkpoint: str | None = None):
        """Read-only common contract: checkpoint is a search keyword."""
        params = search_params(checkpoint, 3)
        payload = self.transport.get(search_url(params))
        parse_response(payload, 3)
        fingerprint = hashlib.sha256(search_url(params).encode()).hexdigest()
        yield SourceRecord(fingerprint, payload, "application/json")

    def _save_document(self, session, item: SearchDocument, raw_id: str) -> str:
        existing = session.scalar(select(FederalRegisterDocument).where(
            FederalRegisterDocument.source == self.name,
            FederalRegisterDocument.external_id == item.number))
        fields = {"title": item.title, "document_type": item.document_type,
                  "publication_date": item.publication_date, "agency_names": item.agency_names,
                  "html_url": item.html_url}
        if existing is None:
            doc = FederalRegisterDocument(source=self.name, external_id=item.number,
                                          raw_document_id=raw_id, **fields)
            session.add(doc)
            session.flush()
            audit(session, "fr_document.created", "federal_register_document", doc.id,
                  {"document_number": item.number, "raw_document_id": raw_id})
            return "saved"
        changes = {k: {"old": getattr(existing, k), "new": value}
                   for k, value in fields.items() if getattr(existing, k) != value}
        if changes:
            old_raw = existing.raw_document_id
            for field, value in fields.items():
                setattr(existing, field, value)
            existing.raw_document_id = raw_id
            existing.updated_at = now()
            audit(session, "fr_document.updated", "federal_register_document", existing.id,
                  {"changes": changes, "old_raw_document_id": old_raw, "new_raw_document_id": raw_id})
            return "updated"
        return "duplicate"

    def run(self, keyword: str, run_key: str, *, limit: int = 3) -> RunResult:
        params = search_params(keyword, limit)
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        url = search_url(params)
        fingerprint = hashlib.sha256(url.encode()).hexdigest()

        def work(progress):
            payload = self.transport.get(url)
            docs = parse_response(payload, limit)  # Validate before committing raw or metadata.
            with self.sf.begin() as session:
                raw = ingest(self.settings, session, "federal_register.search",
                             SourceRecord(fingerprint, payload, "application/json"))
                raw_id = raw.id
                audit(session, "federal_register.search", "raw_document", raw_id,
                      {"keyword": keyword.strip(), "url": url, "query_sha256": fingerprint})
            for item in docs:
                with self.sf.begin() as session:
                    outcome = self._save_document(session, item, raw_id)
                if outcome == "saved":
                    progress.saved += 1
                elif outcome == "updated":
                    progress.updated += 1
                else:
                    progress.duplicates += 1

        return execute_run(self.sf, self.name, f"{fingerprint}:{run_key}", work)
