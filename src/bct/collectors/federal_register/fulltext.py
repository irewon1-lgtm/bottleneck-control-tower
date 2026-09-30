"""Fetch only previously indexed Federal Register documents' original text bytes."""
import argparse
import re
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import MalformedRecord, RunResult, SourceRecord, execute_run
from bct.config import Settings, load_settings
from bct.core import audit, ingest
from bct.db import session_factory
from bct.models import FederalRegisterDocument, FederalRegisterFullText

NUMBER = re.compile(r"^[A-Za-z0-9-]{3,80}$")
BASE = "https://www.federalregister.gov/documents/full_text/text/"


def full_text_url(number: str, published: str) -> str:
    if not isinstance(number, str) or not NUMBER.fullmatch(number):
        raise ValueError("invalid document number")
    valid_date = date.fromisoformat(published)
    return f"{BASE}{valid_date:%Y/%m/%d}/{number}.txt"


class FullTextTransport:
    def __init__(self, *, timeout_seconds: int = 25, max_bytes: int = 2_000_000):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if not url.startswith(BASE):
            raise ValueError("unexpected full-text URL")
        request = Request(url, headers={"Accept": "text/plain", "User-Agent": "BottleneckControlTower/0.5"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 200 or response.geturl() != url:
                raise IOError("unexpected full-text response")
            if not response.headers.get("Content-Type", "").lower().startswith("text/plain"):
                raise MalformedRecord("full-text response is not text/plain")
            content = response.read(self.max_bytes + 1)
        if len(content) > self.max_bytes:
            raise IOError("full text exceeded max_bytes")
        return content


def fetch_full_text(settings: Settings, number: str, run_key: str,
                    transport: FullTextTransport | None = None) -> RunResult:
    if not isinstance(number, str) or not NUMBER.fullmatch(number):
        raise ValueError("invalid document number")
    if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
        raise ValueError("invalid run key")
    sf = session_factory(settings)
    transport = transport or FullTextTransport()

    def work(progress):
        with sf() as session:
            doc = session.scalar(select(FederalRegisterDocument).where(
                FederalRegisterDocument.source == "federal_register",
                FederalRegisterDocument.external_id == number,
                FederalRegisterDocument.status == "active"))
            if doc is None:
                raise ValueError("active Federal Register document not found")
            document_id = doc.id
            url = full_text_url(number, doc.publication_date)
        content = transport.get(url)
        if not isinstance(content, bytes) or not content or number.encode("ascii") not in content:
            raise MalformedRecord("empty or mismatched Federal Register full text")
        with sf.begin() as session:
            raw = ingest(settings, session, "federal_register.full_text",
                         SourceRecord(number, content, "text/plain"))
            link = session.scalar(select(FederalRegisterFullText).where(
                FederalRegisterFullText.document_id == document_id,
                FederalRegisterFullText.raw_document_id == raw.id))
            if link is None:
                link = FederalRegisterFullText(document_id=document_id, raw_document_id=raw.id,
                                               source_url=url)
                session.add(link)
                session.flush()
                audit(session, "fr_full_text.linked", "federal_register_full_text", link.id,
                      {"document_id": document_id, "raw_document_id": raw.id,
                       "source_url": url, "sha256": raw.sha256})
                progress.saved += 1
            else:
                progress.duplicates += 1

    return execute_run(sf, "federal_register_full_text", f"{number}:{run_key}", work)


def main():
    parser = argparse.ArgumentParser(description="Save one indexed Federal Register original text")
    parser.add_argument("number")
    parser.add_argument("run_key")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    result = fetch_full_text(load_settings(args.config), args.number, args.run_key)
    print(result)
    if result.status != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
