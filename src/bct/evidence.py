"""Manual classification of an existing Claim-document connection."""
from sqlalchemy import select

from .core import audit
from .models import Candidate, Claim, ClaimDocumentLink, ContractAward, Document, Evidence, FederalRegisterDocument, ResearchDocument, now

DIRECTIONS = frozenset({"SUPPORT", "CONTRADICT", "NEUTRAL"})


def _active_link(session, link_id: str) -> ClaimDocumentLink:
    link = session.get(ClaimDocumentLink, link_id)
    if link is None or link.status != "active":
        raise ValueError("active Claim-document link required")
    claim = session.get(Claim, link.claim_id)
    if claim is None or claim.status != "active" or session.get(Candidate, claim.candidate_id).status != "active":
        raise ValueError("active Claim and Candidate required")
    for attribute, model in (("sec_document_id", Document),
                             ("contract_award_id", ContractAward),
                             ("federal_register_document_id", FederalRegisterDocument),
                             ("research_document_id", ResearchDocument)):
        document_id = getattr(link, attribute)
        if document_id is not None and session.get(model, document_id).status != "active":
            raise ValueError("active document required")
    return link


def _values(direction: str, note: str | None) -> tuple[str, str | None]:
    if not isinstance(direction, str) or direction not in DIRECTIONS:
        raise ValueError("invalid evidence direction")
    if note is not None and (not isinstance(note, str) or len(note) > 1000):
        raise ValueError("invalid evidence note")
    return direction, note


def record_evidence(session, link_id: str, direction: str, note: str | None = None) -> Evidence:
    direction, note = _values(direction, note)
    link = _active_link(session, link_id)
    existing = session.scalar(select(Evidence).where(Evidence.claim_document_link_id == link_id))
    if existing:
        if existing.status != "active" or (existing.direction, existing.note) != (direction, note):
            raise ValueError("existing evidence differs or is deleted; revise or restore explicitly")
        return existing
    item = Evidence(claim_document_link_id=link_id, direction=direction, note=note)
    session.add(item)
    session.flush()
    audit(session, "evidence.created", "evidence", item.id,
          {"claim_id": link.claim_id, "link_id": link_id, "direction": direction, "note": note})
    return item


def revise_evidence(session, item: Evidence, direction: str, note: str | None = None) -> None:
    direction, note = _values(direction, note)
    if item.status != "active":
        raise ValueError("active evidence required")
    _active_link(session, item.claim_document_link_id)
    if (item.direction, item.note) == (direction, note):
        return
    old = {"direction": item.direction, "note": item.note}
    item.direction, item.note, item.updated_at = direction, note, now()
    audit(session, "evidence.revised", "evidence", item.id,
          {"old": old, "new": {"direction": direction, "note": note}})


def set_deleted(session, item: Evidence, deleted: bool) -> None:
    if not isinstance(item, Evidence) or type(deleted) is not bool:
        raise ValueError("invalid evidence or deletion flag")
    if not deleted:
        _active_link(session, item.claim_document_link_id)
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, "evidence.deleted" if deleted else "evidence.restored", "evidence", item.id, {})
