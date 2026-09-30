"""Manual testable Actor labels and links, without name resolution."""
from sqlalchemy import select

from .core import audit
from .models import Actor, ActorDocument, ContractAward, Document, FederalRegisterDocument, ResearchDocument, now

ACTOR_TYPES = frozenset({"COMPANY", "GOVERNMENT", "CUSTOMER", "SUPPLIER", "COMPETITOR", "OTHER"})
DOCUMENT_TYPES = {
    "sec": ("sec_document_id", Document),
    "usaspending": ("contract_award_id", ContractAward),
    "federal_register": ("federal_register_document_id", FederalRegisterDocument),
    "research": ("research_document_id", ResearchDocument),
}


def _text(value: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid Actor text")
    return value.strip()


def put_actor(session, stable_key: str, display_name: str, actor_type: str,
              *, is_test: bool = False) -> Actor:
    stable_key, display_name = _text(stable_key, 200), _text(display_name, 500)
    if not isinstance(actor_type, str) or actor_type not in ACTOR_TYPES:
        raise ValueError("invalid Actor type")
    if type(is_test) is not bool:
        raise ValueError("is_test must be boolean")
    existing = session.scalar(select(Actor).where(Actor.stable_key == stable_key))
    if existing:
        if existing.status != "active" or (existing.display_name, existing.actor_type, existing.is_test) != (display_name, actor_type, is_test):
            raise ValueError("existing Actor differs or is deleted")
        return existing
    item = Actor(stable_key=stable_key, display_name=display_name,
                 actor_type=actor_type, is_test=is_test)
    session.add(item)
    session.flush()
    audit(session, "actor.created", "actor", item.id,
          {"stable_key": stable_key, "actor_type": actor_type, "is_test": is_test})
    return item


def link_document(session, actor_id: str, source: str, document_id: str) -> ActorDocument:
    if source not in DOCUMENT_TYPES:
        raise ValueError("unknown document source")
    actor = session.get(Actor, actor_id)
    if actor is None or actor.status != "active":
        raise ValueError("active Actor required")
    column, model = DOCUMENT_TYPES[source]
    document = session.get(model, document_id)
    if document is None or document.source != source or document.status != "active":
        raise ValueError("active source document required")
    existing = session.scalar(select(ActorDocument).where(
        ActorDocument.actor_id == actor_id, getattr(ActorDocument, column) == document_id))
    if existing:
        if existing.status != "active":
            raise ValueError("link is deleted; restore explicitly")
        return existing
    item = ActorDocument(actor_id=actor_id, **{column: document_id})
    session.add(item)
    session.flush()
    audit(session, "actor_document.linked", "actor_document", item.id,
          {"actor_id": actor_id, "source": source, "document_id": document_id})
    return item


def set_deleted(session, item: Actor | ActorDocument, deleted: bool) -> None:
    kind = {Actor: "actor", ActorDocument: "actor_document"}.get(type(item))
    if kind is None or type(deleted) is not bool:
        raise ValueError("invalid Actor object or deletion flag")
    if not deleted and isinstance(item, ActorDocument):
        parent = session.get(Actor, item.actor_id)
        if parent is None or parent.status != "active":
            raise ValueError("restore parent Actor first")
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, f"{kind}.{'deleted' if deleted else 'restored'}", kind, item.id, {})
