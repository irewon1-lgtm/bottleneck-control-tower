"""Manual public-document intake for the pilot; no crawler or classification."""
from datetime import date

from sqlalchemy import select

from .collector import SourceRecord
from .core import audit, ingest
from .models import ResearchDocument, now


def put_research_document(settings, session, source_url: str, title: str,
                          publisher: str, content: bytes, *, published_on: str | None = None):
    if not isinstance(source_url, str) or not source_url.startswith("https://") or len(source_url) > 500:
        raise ValueError("invalid research URL")
    if not isinstance(title, str) or not title.strip() or len(title) > 1000:
        raise ValueError("invalid title")
    if not isinstance(publisher, str) or not publisher.strip() or len(publisher) > 300:
        raise ValueError("invalid publisher")
    if published_on is not None and (not isinstance(published_on, str) or
            date.fromisoformat(published_on).isoformat() != published_on):
        raise ValueError("invalid publication date")
    # The caller supplies retrieved original bytes. Never fabricate a source from notes.
    raw = ingest(settings, session, "research", SourceRecord(source_url, content, "text/html"))
    item = session.scalar(select(ResearchDocument).where(
        ResearchDocument.source_url == source_url,
        ResearchDocument.raw_document_id == raw.id))
    if item:
        if item.status != "active" or (item.title, item.publisher, item.published_on) != (
                title, publisher, published_on):
            raise ValueError("research document differs or is deleted")
        return item
    item = ResearchDocument(source_url=source_url, title=title, publisher=publisher,
                            published_on=published_on, raw_document_id=raw.id)
    session.add(item)
    session.flush()
    audit(session, "research_document.created", "research_document", item.id,
          {"source_url": source_url, "sha256": raw.sha256, "publisher": publisher})
    return item


def set_deleted(session, item: ResearchDocument, deleted: bool) -> None:
    if not isinstance(item, ResearchDocument) or type(deleted) is not bool:
        raise ValueError("invalid research document or deletion flag")
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, "research_document.deleted" if deleted else "research_document.restored",
          "research_document", item.id, {})
