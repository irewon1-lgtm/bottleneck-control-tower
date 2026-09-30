"""Manual RADAR Core decisions in the existing append-only audit log."""
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from .core import audit
from .models import AuditLog, RadarItem

TRIGGERS = {
    "NEW_INDEPENDENT_CONSTRAINT",
    "SCOPE_EXPANSION",
    "METRIC_WORSENING",
    "RECOVERY",
}


def _key(family: str) -> str:
    return str(uuid5(NAMESPACE_URL, "bct:radar-family:" + family))


def _history(session, family: str) -> list[AuditLog]:
    return session.scalars(select(AuditLog).where(
        AuditLog.object_type == "radar_family", AuditLog.object_id == _key(family))
        .order_by(AuditLog.created_at, AuditLog.id)).all()


def current(session, family: str) -> dict | None:
    review = None
    pending = []
    for event in _history(session, family):
        if event.event == "radar_family.review":
            review = json.loads(event.details_json)
            pending = []
        elif event.event == "radar_family.material_change" and review is not None:
            pending.append(json.loads(event.details_json))
    if review is None:
        return None
    return {**review, "pending_changes": pending, "re_review_required": bool(pending)}


def record_review(session, family: str, *, status: str, confirmed_scope: list[str],
                  unresolved_scope: list[str], reviewed_article_ids: list[str],
                  lineage_roots: list[str], review_note: str) -> bool:
    if status not in {"WATCH", "KEEP_PROMOTED", "REJECT"}:
        raise ValueError("invalid Core review status")
    if not family.strip() or not review_note.strip() or not reviewed_article_ids:
        raise ValueError("review needs a family, note and reviewed articles")
    if set(confirmed_scope) & set(unresolved_scope):
        raise ValueError("confirmed and unresolved scope overlap")
    ids = sorted(set(reviewed_article_ids))
    if len(session.scalars(select(RadarItem.id).where(RadarItem.id.in_(ids))).all()) != len(ids):
        raise ValueError("review article missing from RADAR")
    details = {"family": family, "status": status,
               "confirmed_scope": sorted(set(confirmed_scope)),
               "unresolved_scope": sorted(set(unresolved_scope)),
               "reviewed_article_ids": ids,
               "lineage_roots": sorted(set(lineage_roots)), "review_note": review_note}
    previous = current(session, family)
    if previous is not None and not previous["re_review_required"] and all(
            previous.get(k) == value for k, value in details.items()):
        return False
    audit(session, "radar_family.review", "radar_family", _key(family), details)
    session.flush()
    return True


def record_material_change(session, family: str, *, trigger: str, article_id: str,
                           lineage_root: str, note: str, original_measurement: bool,
                           current_fact: bool, product: str | None = None) -> bool:
    """Only a manually checked current, original observation can reopen WATCH."""
    review = current(session, family)
    if review is None:
        raise ValueError("review family before recording a material change")
    if trigger not in TRIGGERS or not lineage_root.strip() or not note.strip():
        raise ValueError("invalid material change")
    if not original_measurement or not current_fact:
        return False  # Conditional language and source reprints cannot reopen it.
    if trigger == "NEW_INDEPENDENT_CONSTRAINT" and lineage_root in review["lineage_roots"]:
        return False
    if trigger == "SCOPE_EXPANSION" and product not in review["unresolved_scope"]:
        return False
    if article_id in review["reviewed_article_ids"] or session.get(RadarItem, article_id) is None:
        return False
    details = {"trigger": trigger, "article_id": article_id, "lineage_root": lineage_root,
               "note": note, "product": product}
    if details in review["pending_changes"]:
        return False
    audit(session, "radar_family.material_change", "radar_family", _key(family), details)
    session.flush()
    return True
