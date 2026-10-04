"""Manual search plans/results tied to a Candidate; performs no searching."""
from datetime import date

from sqlalchemy import select

from .core import audit
from .models import Candidate, CountersearchRun, now

SEARCH_KINDS = frozenset({"SUPPLY_EXPANSION", "NEW_SUPPLIER", "DEMAND_SLOWDOWN",
                          "SUBSTITUTION", "POLICY_CHANGE", "OTHER"})
RESULT_STATUSES = frozenset({"NOT_RUN", "RESULTS_FOUND", "NO_RESULTS", "INCONCLUSIVE", "FAILED"})


def _text(value: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("invalid countersearch text")
    return value.strip()


def put_countersearch(session, candidate_id: str, record_key: str, search_kind: str,
                      query: str, result_status: str = "NOT_RUN", *,
                      executed_on: str | None = None, note: str | None = None) -> CountersearchRun:
    record_key, query = _text(record_key, 200), _text(query, 500)
    if not isinstance(search_kind, str) or search_kind not in SEARCH_KINDS:
        raise ValueError("invalid search kind")
    if not isinstance(result_status, str) or result_status not in RESULT_STATUSES:
        raise ValueError("invalid result status")
    if (result_status == "NOT_RUN") != (executed_on is None):
        raise ValueError("execution date must be absent only for NOT_RUN")
    if executed_on is not None:
        if not isinstance(executed_on, str) or len(executed_on) != 10 or date.fromisoformat(executed_on).isoformat() != executed_on:
            raise ValueError("invalid execution date")
    if note is not None and (not isinstance(note, str) or len(note) > 1000):
        raise ValueError("invalid note")
    candidate = session.get(Candidate, candidate_id)
    if candidate is None or candidate.status != "active":
        raise ValueError("active Candidate required")
    existing = session.scalar(select(CountersearchRun).where(
        CountersearchRun.candidate_id == candidate_id, CountersearchRun.record_key == record_key))
    if existing:
        fields = (existing.search_kind, existing.query, existing.result_status,
                  existing.executed_on, existing.note)
        if existing.status != "active" or fields != (search_kind, query, result_status, executed_on, note):
            raise ValueError("existing search record differs or is deleted")
        return existing
    item = CountersearchRun(candidate_id=candidate_id, record_key=record_key,
                            search_kind=search_kind, query=query, result_status=result_status,
                            executed_on=executed_on, note=note)
    session.add(item)
    session.flush()
    audit(session, "countersearch.created", "countersearch_run", item.id,
          {"candidate_id": candidate_id, "record_key": record_key,
           "search_kind": search_kind, "result_status": result_status,
           "executed_on": executed_on, "query": query, "note": note})
    return item


def set_deleted(session, item: CountersearchRun, deleted: bool) -> None:
    if not isinstance(item, CountersearchRun) or type(deleted) is not bool:
        raise ValueError("invalid search record or deletion flag")
    if not deleted:
        parent = session.get(Candidate, item.candidate_id)
        if parent is None or parent.status != "active":
            raise ValueError("restore Candidate first")
    target = "deleted" if deleted else "active"
    if item.status == target:
        return
    item.status = target
    item.deleted_at = now() if deleted else None
    item.updated_at = now()
    audit(session, "countersearch.deleted" if deleted else "countersearch.restored",
          "countersearch_run", item.id, {})
