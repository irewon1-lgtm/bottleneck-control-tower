"""Source-backed range/date comparison only; no fetching, scoring or DB writes."""
from datetime import date
import calendar
import math


VERSION = "supply-gap-v1"


def _sourced(value, as_of):
    refs = value.get("evidence", [])
    try:
        return bool(value.get("basis") and refs) and all(
            ref["url"].startswith(("https://", "http://"))
            and date.fromisoformat(ref["published_on"]) <= as_of
            and ref.get("locator") for ref in refs)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _bounds(value):
    lo, hi = value.get("min"), value.get("max")
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) or x < 0 for x in (lo, hi)) or lo > hi:
        return None
    return lo, hi


def evaluate(inputs, as_of):
    """Inputs are reviewed claims. URL presence is not independent fact verification.

    Both quantities must describe total demand/supply or incremental demand/free
    supply for identical target, unit and period. Partial supplier coverage can
    never establish a shortage. Keep this result separate from legacy statuses.
    """
    today = date.fromisoformat(as_of)
    horizon = today.replace(year=today.year + 2, day=min(
        today.day, calendar.monthrange(today.year + 2, today.month)[1]))
    result = {"version": VERSION, "as_of": as_of, "gap_status": "UNRESOLVED",
              "route": None, "gap_range": None, "objective_fit": "UNRESOLVED",
              "market_awareness": "UNRESOLVED", "economic_capture": "UNRESOLVED",
              "investment_status": "UNRESOLVED", "blockers": []}
    missing = result["blockers"]
    current = inputs.get("current", {})
    current_known = _sourced(current, today)
    if current_known and current.get("state") == "SHORT":
        result["objective_fit"] = "CURRENT_REFERENCE"
    elif not current_known or current.get("state") != "NOT_SHORT":
        missing.append("현재 같은 규격·지역의 부족 여부 미확인")
    window = inputs.get("shortage_window", {})
    in_window = False
    try:
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        if _sourced(window, today) and start <= end:
            in_window = today < start <= end <= horizon
            if result["objective_fit"] != "CURRENT_REFERENCE" and not in_window:
                result["objective_fit"] = "OUTSIDE_WINDOW"
    except (KeyError, TypeError, ValueError):
        pass
    if not in_window:
        missing.append("향후 24개월 이내 부족 발생 시점 미확인 또는 범위 밖")

    demand, supply = inputs.get("demand", {}), inputs.get("supply", {})
    db, sb = _bounds(demand), _bounds(supply)
    dimensions = ("scope", "unit", "period_start", "period_end", "balance_basis")
    aligned = all(demand.get(k) and demand.get(k) == supply.get(k) for k in dimensions)
    try:
        period_ok = date.fromisoformat(demand["period_start"]) <= date.fromisoformat(demand["period_end"])
    except (KeyError, TypeError, ValueError):
        period_ok = False
    quantity_ok = (db and sb and aligned and period_ok
                   and demand.get("balance_basis") in ("total", "incremental_free")
                   and _sourced(demand, today) and _sourced(supply, today)
                   and supply.get("coverage") == "ALL_FEASIBLE_SUPPLIERS"
                   and supply.get("kind") == "QUALIFIED_DELIVERABLE")
    if quantity_ok:
        gap = [db[0] - sb[1], db[1] - sb[0]]
        result.update(gap_range=gap, route="QUANTITY", unit=demand["unit"],
                      gap_status="GAP_SUPPORTED" if gap[0] > 0 else
                      "NO_GAP_IN_RANGE" if gap[1] <= 0 else "GAP_CONDITIONAL")
    else:
        missing.append("동일 규격·기간·단위의 수요량과 전체 적격 공급량 범위 미확인")
    timing = inputs.get("timing", {})
    timing_ok = False
    try:
        required = date.fromisoformat(timing["required_by"])
        earliest = date.fromisoformat(timing["earliest_qualified_supply"])
        timing_ok = (_sourced(timing, today) and timing.get("coverage") == "ALL_FEASIBLE_SUPPLIERS"
                     and today < required <= horizon and required < earliest)
    except (KeyError, TypeError, ValueError):
        pass
    if timing_ok and result["gap_status"] == "NO_GAP_IN_RANGE":
        result.update(gap_status="UNRESOLVED", route=None)
        missing.append("수량 근거와 일정 근거 충돌: 기간·범위 재확인")
    elif timing_ok:
        result.update(gap_status="GAP_SUPPORTED", route="TIMING" if not quantity_ok else "QUANTITY_AND_TIMING")
    elif not quantity_ok:
        missing.append("고객 필요일과 전체 대체 공급의 가장 빠른 적격 납기 미확인")
    relief = inputs.get("relief", {})
    relief_ok = relief.get("review_complete") is True and _sourced(relief, today)
    if not relief_ok:
        missing.append("경쟁 증설·대체 공급·재고·수요 지연 반증 점검 미완료")
    quantity_window_ok = (in_window and quantity_ok and demand["period_start"] <= window["start"]
                          <= window["end"] <= demand["period_end"])
    timing_window_ok = (in_window and timing_ok and window["start"] <= timing["required_by"]
                       <= window["end"])
    if quantity_ok and in_window and not quantity_window_ok:
        missing.append("수량 비교 기간과 예상 부족 발생 기간 불일치")
    if (result["gap_status"] == "GAP_SUPPORTED" and in_window and relief_ok
            and (timing_window_ok or quantity_window_ok)
            and current_known and current.get("state") == "NOT_SHORT"):
        result["objective_fit"] = "FUTURE_MATCH"
    for field in ("market_awareness", "economic_capture"):
        value = inputs.get(field, {})
        if _sourced(value, today):
            result[field] = value.get("state", "UNRESOLVED")
    # Low public awareness alone cannot establish that a stock is mispriced.
    missing.append("기업별 이익 귀속·가치평가·주가 선반영은 별도 검증")
    return result
