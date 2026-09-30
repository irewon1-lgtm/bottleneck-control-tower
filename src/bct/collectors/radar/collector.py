"""GDELT DOC article-list intake. An item is a lead, not evidence."""
import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import MalformedRecord, RunResult, execute_run
from bct.config import Settings
from bct.core import audit
from bct.db import session_factory
from bct.models import RadarItem, now

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERIES = ("shortage", '"lead time"', '"capacity constrained"',
           '"qualification delay"', '"unable to meet demand"')


def feed_url(limit: int, query: str = "shortage") -> str:
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("limit must be 1..25")
    if query not in QUERIES:
        raise ValueError("unsupported discovery query")
    return ENDPOINT + "?" + urlencode({"query": query, "mode": "artlist", "format": "json",
                                       "timespan": "24h", "sort": "datedesc", "maxrecords": limit})


@dataclass(frozen=True)
class FeedItem:
    source: str
    external_id: str
    title: str
    url: str
    published_at: str | None = None
    snippet: str | None = None
    source_type: str = "NEWS"


def parse_response(payload: bytes, limit: int) -> list[FeedItem]:
    try:
        data = json.loads(payload)
        rows = data["articles"]
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError("invalid articles")
        items = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid article")
            title, url = row["title"], row["url"]
            if not isinstance(title, str) or not title.strip() or len(title) > 2000:
                raise ValueError("invalid title")
            if not isinstance(url, str) or len(url) > 2000:
                raise ValueError("invalid url")
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
                raise ValueError("invalid article URL")
            # A fragment is local navigation, not a new article; preserve its query string.
            canonical = urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                                    parts.path, parts.query, ""))
            source = parts.hostname.lower()
            if len(source) > 120:
                raise ValueError("invalid source domain")
            items.append(FeedItem(source, hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                                  title.strip(), canonical))
        return items
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeDecodeError) as exc:
        raise MalformedRecord(f"invalid GDELT response: {exc}") from exc


class GDELTTransport:
    def __init__(self, timeout_seconds: int = 25, max_bytes: int = 2_000_000):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if not url.startswith(ENDPOINT + "?"):
            raise ValueError("invalid GDELT URL")
        request = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "BottleneckControlTower/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise IOError(f"GDELT HTTP {response.status}")
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise IOError("GDELT response exceeded max_bytes")
        return payload


class RadarCollector:
    name = "radar_gdelt"

    def __init__(self, settings: Settings, transport: GDELTTransport):
        self.sf = session_factory(settings)
        self.transport = transport

    def _save_item(self, session, item: FeedItem) -> str:
        existing = session.scalar(select(RadarItem).where(
            RadarItem.source == item.source, RadarItem.external_id == item.external_id))
        if existing is None:
            record = RadarItem(source=item.source, external_id=item.external_id, title=item.title,
                               url=item.url, published_at=item.published_at, snippet=item.snippet,
                               source_type=item.source_type)
            session.add(record)
            session.flush()
            audit(session, "radar.created", "radar_item", record.id,
                  {"source": item.source, "external_id": item.external_id, "title": item.title,
                   "url": item.url})
            return "saved"
        if existing.status != "active":
            # A previously deleted lead cannot be revived by a background feed.
            return "duplicate"
        fields = ("title", "url", "published_at", "snippet", "source_type")
        changes = {field: {"old": getattr(existing, field), "new": getattr(item, field)}
                   for field in fields if getattr(existing, field) != getattr(item, field)}
        if not changes:
            return "duplicate"
        for field in changes:
            setattr(existing, field, getattr(item, field))
        existing.updated_at = now()
        audit(session, "radar.updated", "radar_item", existing.id, {"changes": changes})
        return "updated"

    def run(self, run_key: str, *, limit: int = 10, query: str = "shortage") -> RunResult:
        url = feed_url(limit, query)
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        query_id = hashlib.sha256(url.encode()).hexdigest()

        def work(progress):
            items = parse_response(self.transport.get(url), limit)  # Entire page before DB writes.
            for item in items:
                with self.sf.begin() as session:
                    outcome = self._save_item(session, item)
                if outcome == "saved":
                    progress.saved += 1
                elif outcome == "updated":
                    progress.updated += 1
                else:
                    progress.duplicates += 1

        return execute_run(self.sf, self.name, f"{query_id}:{run_key}", work)
