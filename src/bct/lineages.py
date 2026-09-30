"""Manual, explicitly marked groups of indexed documents."""
from sqlalchemy import select

from .core import audit
from .models import ContractAward, Document, FederalRegisterDocument, ResearchDocument, Lineage, LineageDocument, now

DOCUMENT_TYPES = {
    "sec": ("sec_document_id", Document),
    "usaspending": ("contract_award_id", ContractAward),
    "federal_register": ("federal_register_document_id", FederalRegisterDocument),
    "research": ("research_document_id", ResearchDocument),
}


def _text(value: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid lineage text")
    return value.strip()


def put_lineage(session, stable_key: str, label: str, *, is_test: bool = False) -> Lineage:
    stable_key, label = _text(stable_key, 200), _text(label, 500)
    if type(is_test) is not bool:
        raise ValueError("is_test must be boolean")
    existing = session.scalar(select(Lineage).where(Lineage.stable_key == stable_key))
    if existing:
        if existing.status != "active" or (existing.label, existing.is_test) != (label, is_test):
            raise ValueError("existing Lineage differs or is deleted")
        return existing
    item = Lineage(stable_key=stable_key, label=label, is_test=is_test)
    session.add(item)
    session.flush()
    audit(session, "lineage.created", "lineage", item.id,
          {"stable_key": stable_key, "is_test": is_test})
    return item


def link_document(session, lineage_id: str, source: str, document_id: str) -> LineageDocument:
    if source not in DOCUMENT_TYPES:
        raise ValueError("unknown document source")
    lineage = session.get(Lineage, lineage_id)
    if lineage is None or lineage.status != "active":
        raise ValueError("active Lineage required")
    column, model = DOCUMENT_TYPES[source]
    document = session.get(model, document_id)
    if document is None or document.source != source or document.status != "active":
        raise ValueError("active source document required")
    existing = session.scalar(select(LineageDocument).where(
        LineageDocument.lineage_id == lineage_id, getattr(LineageDocument, column) == document_id))
    if existing:
        if existing.status != "active":
            raise ValueError("link is deleted; restore explicitly")
        return existing
    item = LineageDocument(lineage_id=lineage_id, **{column: document_id})
    session.add(item)
    session.flush()
    audit(session, "lineage_document.linked", "lineage_document", item.id,
          {"lineage_id": lineage_id, "source": source, "document_id": document_id})
    return item


def set_deleted(session, item: Lineage | LineageDocument, deleted: bool) -> None:
    kind = {Lineage: "lineage", LineageDocument: "lineage_document"}.get(type(item))
    if kind is None or type(deleted) is not bool:
        raise ValueError("invalid Lineage object or deletion flag")
    if not deleted and isinstance(item, LineageDocument):
        parent = session.get(Lineage, item.lineage_id)
        if parent is None or parent.status != "active":
            raise ValueError("restore parent Lineage first")
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, f"{kind}.{'deleted' if deleted else 'restored'}", kind, item.id, {})
