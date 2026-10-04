import hashlib
import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import Collector, MalformedRecord, SourceRecord, RunResult, execute_run
from bct.config import Settings
from bct.core import audit, ingest
from bct.db import session_factory
from bct.models import ContractAward, now

ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
          "Last Modified Date", "generated_internal_id"]
CONTRACT_TYPES = ["A", "B", "C", "D"]


@dataclass(frozen=True)
class Award:
    external_id: str
    award_id: str
    recipient_name: str
    award_amount: str | None
    awarding_agency: str | None
    last_modified_date: str | None


def request_body(query: str, mode: str, limit: int) -> dict:
    if mode not in ("company", "keyword"):
        raise ValueError("mode must be company or keyword")
    if not isinstance(query, str) or not query.strip() or len(query) > 150:
        raise ValueError("query must be 1..150 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    filters = {"award_type_codes": CONTRACT_TYPES,
               "recipient_search_text" if mode == "company" else "keywords": [query.strip()]}
    return {"filters": filters, "fields": FIELDS, "page": 1, "limit": limit,
            "sort": "Award Amount", "order": "desc"}


def request_bytes(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _optional_text(value, field: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"invalid {field}")
    return value


def parse_response(payload: bytes, limit: int) -> list[Award]:
    try:
        data = json.loads(payload)
        rows = data["results"]
        if data.get("spending_level") != "awards" or not isinstance(rows, list) or len(rows) > limit:
            raise ValueError("invalid award results")
        awards = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("generated_internal_id"), str):
                raise ValueError("missing generated_internal_id")
            external = row["generated_internal_id"]
            award_id = row["Award ID"]
            recipient = row["Recipient Name"]
            if not external.strip() or len(external) > 500 or not isinstance(award_id, str) or not award_id.strip() or len(award_id) > 160 or not isinstance(recipient, str) or not recipient.strip() or len(recipient) > 500:
                raise ValueError("missing or invalid award identity")
            amount = row.get("Award Amount")
            if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float))):
                raise ValueError("invalid Award Amount")
            awards.append(Award(external, award_id, recipient, str(amount) if amount is not None else None,
                _optional_text(row.get("Awarding Agency"), "Awarding Agency", 300),
                _optional_text(row.get("Last Modified Date"), "Last Modified Date", 40)))
        return awards
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise MalformedRecord(f"invalid USAspending response: {exc}") from exc


class USAspendingTransport:
    def __init__(self, *, timeout_seconds: int = 30, max_bytes: int = 4_000_000):
        if timeout_seconds <= 0 or max_bytes < 1024:
            raise ValueError("invalid transport limits")
        self.timeout = timeout_seconds
        self.max_bytes = max_bytes

    def post(self, body: dict) -> bytes:
        request = Request(ENDPOINT, data=request_bytes(body),
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "User-Agent": "BottleneckControlTower/0.3"}, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise IOError(f"USAspending HTTP {response.status}")
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise IOError("USAspending response exceeded max_bytes")
        return payload


class USAspendingCollector(Collector):
    name = "usaspending"

    def __init__(self, settings: Settings, transport: USAspendingTransport):
        self.settings = settings
        self.transport = transport
        self.sf = session_factory(settings)

    def collect(self, checkpoint: str | None = None):
        """Common contract: checkpoint is 'company:TEXT' or 'keyword:TEXT'."""
        if not checkpoint or ":" not in checkpoint:
            raise ValueError("checkpoint must be company:TEXT or keyword:TEXT")
        mode, query = checkpoint.split(":", 1)
        body = request_body(query, mode, 3)
        payload = self.transport.post(body)
        parse_response(payload, 3)
        yield SourceRecord(hashlib.sha256(request_bytes(body)).hexdigest(), payload, "application/json")

    def _save_award(self, session, award: Award, raw_id: str) -> str:
        existing = session.scalar(select(ContractAward).where(ContractAward.source == self.name,
                                                               ContractAward.external_id == award.external_id))
        fields = {"award_id": award.award_id, "recipient_name": award.recipient_name,
                  "award_amount": award.award_amount, "awarding_agency": award.awarding_agency,
                  "last_modified_date": award.last_modified_date}
        if existing is None:
            item = ContractAward(source=self.name, external_id=award.external_id,
                                 raw_document_id=raw_id, **fields)
            session.add(item)
            session.flush()
            audit(session, "contract_award.created", "contract_award", item.id,
                  {"external_id": award.external_id, "raw_document_id": raw_id})
            return "saved"
        changes = {field: {"old": getattr(existing, field), "new": value}
                   for field, value in fields.items() if getattr(existing, field) != value}
        if changes:
            old_raw = existing.raw_document_id
            for field, value in fields.items():
                setattr(existing, field, value)
            existing.raw_document_id = raw_id
            existing.updated_at = now()
            audit(session, "contract_award.updated", "contract_award", existing.id,
                  {"changes": changes, "old_raw_document_id": old_raw, "new_raw_document_id": raw_id})
            return "updated"
        return "duplicate"

    def run(self, query: str, run_key: str, *, mode: str = "company", limit: int = 3) -> RunResult:
        body = request_body(query, mode, limit)
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        fingerprint = hashlib.sha256(request_bytes(body)).hexdigest()

        def work(progress):
            payload = self.transport.post(body)
            awards = parse_response(payload, limit)  # Validate all rows before any write.
            with self.sf.begin() as session:
                raw = ingest(self.settings, session, "usaspending.search",
                             SourceRecord(fingerprint, payload, "application/json"))
                raw_id = raw.id
                audit(session, "usaspending.search", "raw_document", raw_id,
                      {"request": body, "query_sha256": fingerprint})
            for award in awards:
                with self.sf.begin() as session:
                    outcome = self._save_award(session, award, raw_id)
                if outcome == "saved":
                    progress.saved += 1
                elif outcome == "updated":
                    progress.updated += 1
                else:
                    progress.duplicates += 1

        return execute_run(self.sf, self.name, f"{fingerprint}:{run_key}", work)
