"""RSS/Atom metadata intake; article bodies are not downloaded."""
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from sqlalchemy import select

from bct.collector import MalformedRecord, RunResult, execute_run
from bct.config import Settings
from bct.core import audit
from bct.db import session_factory
from bct.models import RadarItem, now

ATOM = "{http://www.w3.org/2005/Atom}"


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


@dataclass(frozen=True)
class RSSItem:
    source: str
    external_id: str
    title: str
    url: str
    published_at: str | None
    snippet: str | None


def _date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MalformedRecord("invalid feed date") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(payload: bytes, limit: int) -> list[RSSItem]:
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise MalformedRecord("feed DTD is not allowed")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise MalformedRecord("invalid feed XML") from exc
    if root.tag == "rss":
        entries = root.findall("./channel/item")
        atom = False
    elif root.tag == "{http://www.w3.org/2005/Atom}feed":
        entries = root.findall(f"{ATOM}entry")
        atom = True
    elif root.tag == "{http://purl.org/rss/1.0/}RDF":
        entries = root.findall("{http://purl.org/rss/1.0/}item")
        atom = False
    else:
        raise MalformedRecord("unsupported feed format")
    if not entries:
        raise MalformedRecord("feed has no entries")
    output = []
    for entry in entries[:limit]:
        ns = "{http://purl.org/rss/1.0/}" if root.tag.endswith("}RDF") else ""
        title = entry.findtext(f"{ATOM}title" if atom else f"{ns}title")
        if atom:
            links = [link.get("href") for link in entry.findall(f"{ATOM}link")
                     if link.get("rel", "alternate") == "alternate"]
            url = links[0] if links else None
            published = entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
            summary = entry.findtext(f"{ATOM}summary")
        else:
            url = entry.findtext(f"{ns}link")
            published = entry.findtext("pubDate") or entry.findtext(f"{ns}date")
            summary = entry.findtext("description") or entry.findtext(f"{ns}description")
        if not title or not title.strip() or len(title.strip()) > 2000:
            raise MalformedRecord("invalid feed title")
        if not url or not isinstance(url, str) or len(url) > 2000:
            raise MalformedRecord("invalid feed article URL")
        parts = urlsplit(url.strip())
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise MalformedRecord("invalid feed article URL")
        canonical = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
        source = parts.hostname.lower()
        if len(source) > 120:
            raise MalformedRecord("invalid feed source")
        plain = None
        if summary:
            stripper = _PlainText()
            stripper.feed(summary)
            plain = " ".join(" ".join(stripper.parts).split())[:1000] or None
        output.append(RSSItem(source, hashlib.sha256(canonical.encode()).hexdigest(),
                              title.strip(), canonical, _date(published), plain))
    return output


class RSSTransport:
    def __init__(self, timeout_seconds: int = 12, max_bytes: int = 2_000_000):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if urlsplit(url).scheme != "https":
            raise ValueError("RSS feed URL must use HTTPS")
        request = Request(url, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                                        "User-Agent": "BottleneckControlTower/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise IOError(f"RSS HTTP {response.status}")
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise IOError("RSS feed exceeded max_bytes")
        return payload


class RSSCollector:
    name = "radar_rss"

    def __init__(self, settings: Settings, transport: RSSTransport):
        self.sf = session_factory(settings)
        self.transport = transport

    def _save(self, session, item: RSSItem) -> str:
        existing = session.scalar(select(RadarItem).where(
            RadarItem.source == item.source, RadarItem.external_id == item.external_id))
        if existing is None:
            row = RadarItem(source=item.source, external_id=item.external_id,
                            title=item.title, url=item.url, published_at=item.published_at,
                            snippet=item.snippet, source_type="NEWS")
            session.add(row)
            session.flush()
            audit(session, "radar.created", "radar_item", row.id,
                  {"source": item.source, "external_id": item.external_id,
                   "title": item.title, "url": item.url})
            return "saved"
        if existing.status != "active":
            return "duplicate"
        fields = ("title", "url", "published_at", "snippet", "source_type")
        incoming = {"title": item.title, "url": item.url,
                    "published_at": item.published_at, "snippet": item.snippet,
                    "source_type": "NEWS"}
        changes = {field: {"old": getattr(existing, field), "new": incoming[field]}
                   for field in fields if getattr(existing, field) != incoming[field]}
        if not changes:
            return "duplicate"
        for field in changes:
            setattr(existing, field, incoming[field])
        existing.updated_at = now()
        audit(session, "radar.updated", "radar_item", existing.id, {"changes": changes})
        return "updated"

    def run(self, feed_url: str, run_key: str, *, limit: int = 5) -> RunResult:
        if urlsplit(feed_url).scheme != "https" or not urlsplit(feed_url).hostname:
            raise ValueError("invalid RSS feed URL")
        if not isinstance(run_key, str) or not run_key.strip() or len(run_key) > 400:
            raise ValueError("invalid run_key")
        feed_id = hashlib.sha256(feed_url.encode()).hexdigest()

        def work(progress):
            items = parse_feed(self.transport.get(feed_url), limit)
            for item in items:
                with self.sf.begin() as session:
                    outcome = self._save(session, item)
                if outcome == "saved":
                    progress.saved += 1
                elif outcome == "updated":
                    progress.updated += 1
                else:
                    progress.duplicates += 1

        return execute_run(self.sf, self.name, f"{feed_id}:{run_key}", work)
