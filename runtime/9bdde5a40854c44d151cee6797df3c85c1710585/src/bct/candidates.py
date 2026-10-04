"""Manual candidate/claim records and pointers to already indexed documents."""
from sqlalchemy import select

from .core import audit
from .models import (Candidate, Claim, ClaimDocumentLink, ContractAward, Document,
                     FederalRegisterDocument, ResearchDocument, now)

DOCUMENT_TYPES = {
    "sec": ("sec_document_id", Document),
    "usaspending": ("contract_award_id", ContractAward),
    "federal_register": ("federal_register_document_id", FederalRegisterDocument),
    "research": ("research_document_id", ResearchDocument),
}


def _text(value: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid text")
    return value.strip()


def put_candidate(session, stable_key: str, display_name: str, *, is_test: bool = False) -> Candidate:
    stable_key = _text(stable_key, 200)
    display_name = _text(display_name, 500)
    if type(is_test) is not bool:
        raise ValueError("is_test must be boolean")
    existing = session.scalar(select(Candidate).where(Candidate.stable_key == stable_key))
    if existing:
        if existing.status != "active" or existing.display_name != display_name or existing.is_test != is_test:
            raise ValueError("existing candidate differs or is deleted")
        return existing
    item = Candidate(stable_key=stable_key, display_name=display_name, is_test=is_test)
    session.add(item)
    session.flush()
    audit(session, "candidate.created", "candidate", item.id,
          {"stable_key": stable_key, "is_test": is_test})
    return item


def put_claim(session, candidate_id: str, statement: str) -> Claim:
    statement = _text(statement, 2000)
    candidate = session.get(Candidate, candidate_id)
    if candidate is None or candidate.status != "active":
        raise ValueError("active candidate required")
    existing = session.scalar(select(Claim).where(Claim.candidate_id == candidate_id,
                                                 Claim.statement == statement))
    if existing:
        if existing.status != "active":
            raise ValueError("claim is deleted; restore it explicitly")
        return existing
    claim = Claim(candidate_id=candidate_id, statement=statement)
    session.add(claim)
    session.flush()
    audit(session, "claim.created", "claim", claim.id, {"candidate_id": candidate_id})
    return claim


def link_document(session, claim_id: str, source: str, document_id: str) -> ClaimDocumentLink:
    if source not in DOCUMENT_TYPES:
        raise ValueError("unknown document source")
    claim = session.get(Claim, claim_id)
    if claim is None or claim.status != "active" or session.get(Candidate, claim.candidate_id).status != "active":
        raise ValueError("active claim and candidate required")
    column, model = DOCUMENT_TYPES[source]
    document = session.get(model, document_id)
    if document is None or document.source != source or document.status != "active":
        raise ValueError("active source document required")
    existing = session.scalar(select(ClaimDocumentLink).where(
        ClaimDocumentLink.claim_id == claim_id, getattr(ClaimDocumentLink, column) == document_id))
    if existing:
        if existing.status != "active":
            raise ValueError("link is deleted; restore it explicitly")
        return existing
    link = ClaimDocumentLink(claim_id=claim_id, **{column: document_id})
    session.add(link)
    session.flush()
    audit(session, "claim_document.linked", "claim_document_link", link.id,
          {"claim_id": claim_id, "source": source, "document_id": document_id})
    return link


def set_deleted(session, item: Candidate | Claim | ClaimDocumentLink, deleted: bool) -> None:
    kinds = {Candidate: "candidate", Claim: "claim", ClaimDocumentLink: "claim_document_link"}
    kind = kinds.get(type(item))
    if kind is None or type(deleted) is not bool:
        raise ValueError("invalid object or deletion flag")
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, f"{kind}.{'deleted' if deleted else 'restored'}", kind, item.id, {})
