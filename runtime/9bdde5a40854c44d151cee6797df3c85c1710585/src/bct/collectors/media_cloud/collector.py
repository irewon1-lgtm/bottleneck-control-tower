"""Small Media Cloud Online News searches; article text is not downloaded."""
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from sqlalchemy import select

from bct.collector import MalformedRecord, RunResult, execute_run
from bct.config import Settings
from bct.core import audit
from bct.db import session_factory
from bct.models import RadarItem, now

ENDPOINT = "https://search.mediacloud.org/api/search/story-list"
QUERIES = ("shortage", '"lead time"', '"capacity constrained"')
US_NATIONAL_COLLECTION = 34412234


def search_url(query: str, limit: int, start: date, end: date) -> str:
    if query not in QUERIES or type(limit) is not int or not 5 <= limit <= 20:
        raise ValueError("invalid Media Cloud query or limit")
    if start > end:
        raise ValueError("start must precede end")
    return ENDPOINT + "?" + urlencode({"q": query, "start": start.isoformat(),
        "end": end.isoformat(), "cs": str(US_NATIONAL_COLLECTION),
        "platform": "online_news", "page_size": limit})


@dataclass(frozen=True)
class Story:
    source: str
    external_id: str
    title: str
    url: str
    published_at: str | None
    snippet: str | None = None
    source_type: str = "NEWS"


def parse_response(payload: bytes, limit: int) -> list[Story]:
    try:
        data = json.loads(payload)
        rows = data["stories"]
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError("invalid stories")
        output = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid story")
            story_id, title, url = row["id"], row["title"], row["url"]
            if not isinstance(story_id, str) or len(story_id) != 64 or any(c not in "0123456789abcdef" for c in story_id):
                raise ValueError("invalid id")
            if not isinstance(title, str) or not title.strip() or len(title) > 2000:
                raise ValueError("invalid title")
            if not isinstance(url, str) or not 1 <= len(url) <= 2000:
                raise ValueError("invalid url")
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("invalid article url")
            source = row.get("media_url") or parsed.hostname
            if not isinstance(source, str) or not source.strip() or len(source) > 120:
                raise ValueError("invalid media_url")
            published = row.get("publish_date")
            if published is not None:
                if not isinstance(published, str) or len(published) != 10:
                    raise ValueError("invalid publish_date")
                date.fromisoformat(published)
            output.append(Story(source.strip().lower(), story_id, title.strip(), url, published))
        return output
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeDecodeError) as exc:
        raise MalformedRecord(f"invalid Media Cloud response: {exc}") from exc


class MediaCloudTransport:
    def __init__(self, api_key: str | None = None, timeout_seconds: int = 25,
                 max_bytes: int = 2_000_000):
        self.api_key = api_key if api_key is not None else os.environ.get("MEDIACLOUD_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if not self.api_key:
            raise RuntimeError("MEDIACLOUD_API_KEY is required")
        if not url.startswith(ENDPOINT + "?"):
            raise ValueError("invalid Media Cloud URL")
        request = Request(url, headers={"Accept": "application/json",
            "Authorization": f"Token {self.api_key}", "User-Agent": "BottleneckControlTower/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise IOError(f"Media Cloud HTTP {response.status}")
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise IOError("Media Cloud response exceeded max_bytes")
        return payload


class MediaCloudCollector:
    name = "radar_media_cloud"

    def __init__(self, settings: Settings, transport: MediaCloudTransport):
        self.sf = session_factory(settings)
        self.transport = transport

    def _save_item(self, session, item: Story) -> str:
        existing = session.scalar(select(RadarItem).where(
            RadarItem.source == item.source, RadarItem.external_id == item.external_id))
        if existing is None:
            record = RadarItem(source=item.source, external_id=item.external_id,
                title=item.title, url=item.url, published_at=item.published_at,
                snippet=item.snippet, source_type=item.source_type)
            session.add(record)
            session.flush()
            audit(session, "radar.created", "radar_item", record.id,
                  {"source": item.source, "external_id": item.external_id,
                   "title": item.title, "url": item.url})
            return "saved"
        if existing.status != "active":
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

    def run(self, query: str, run_key: str, *, limit: int = 5,
            day: date | None = None) -> RunResult:
        day = day or datetime.now(timezone.utc).date()
        url = search_url(query, limit, day - timedelta(days=2), day)
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        request_id = hashlib.sha256(url.encode()).hexdigest()

        def work(progress):
            items = parse_response(self.transport.get(url), limit)
            for item in items:
                with self.sf.begin() as session:
                    outcome = self._save_item(session, item)
                if outcome == "saved":
                    progress.saved += 1
                elif outcome == "updated":
                    progress.updated += 1
                else:
                    progress.duplicates += 1

        return execute_run(self.sf, self.name, f"{request_id}:{run_key}", work)
