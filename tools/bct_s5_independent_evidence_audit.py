"""BCT Session 5: source-free independent evidence triage from verified S4 receipts.

Read-only private epoch access. This is NOT a substitute for two independently
verified primary originals, and never freezes candidates or writes LIVE data.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

FORMAT="bct-s5-original-evidence-triage-v1"
S4_FORMAT="bct-s4-final-11-source-cpu-readback-v1"
S4_ACK="f3018007e6779742bcf9c2dad0e956f1c09138bc"
S4_SQLITE="dee38ca11b1b2fd49b8a0f9c4097b5cdf07d462e41299b2db4503ea6e8e7a7a0"
FIELDS=frozenset(("product","specification","region","customer_group","supply_pool"))
STATES=frozenset(("READ_EVIDENCE_HOLD","NO_VALIDATED_EVENT","RESEARCH_FORECAST_REVIEW"))
COUNTS=("source_bound_event_count","graph_independent_pair_count",
        "strict_pair_count","strict_forecast_candidate_count")
COMPARED=("document_id","body_sha256","raw_sha256","read_state","review_state",
          "reason_code","source_validation","target_review_performed","LIVE_writes")
RECOMMENDATIONS={
    "TARGET_FIELDS_UNKNOWN":"VERIFY_ORIGINAL_PRODUCT_SPEC_REGION_CUSTOMER_AND_QUALIFIED_SUPPLY_SCOPE",
    "CPU_ENTITY_ONLY_SEMANTICS_PENDING":"FIND_EXPLICIT_PRIMARY_DEMAND_OR_ELIGIBLE_SUPPLY_EVENT",
    "QUALIFIED_SUPPLY_SCOPE_UNKNOWN":"VERIFY_ACTUAL_CUSTOMER_QUALIFICATION_AND_UNRESERVED_SUPPLY",
    "INDEPENDENT_COUNTERPART_NOT_VERIFIED":"FIND_INDEPENDENT_ORIGINAL_OPPOSITE_SIDE",
    "NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE":"REVIEW_PRIMARY_ORIGINAL_FOR_EXPLICIT_FUTURE_EVENT",
    "FORECAST_INPUT_NOT_ELIGIBLE":"VERIFY_FUTURE_NEED_AND_QUALIFIED_SUPPLY_TIMING_OR_QUANTITY",
    "EXISTING_STRICT_FORECAST_CANDIDATE_RESEARCH_ONLY":"VERIFY_BOTH_ORIGINALS_BEFORE_ANY_LIVE_ACTION",
}

def fail(reason):
    raise ValueError("S5_"+reason)

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False)

def digest(data):
    if not isinstance(data,bytes):
        data=canonical(data).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def is_hash(value,n):
    return isinstance(value,str) and re.fullmatch("[0-9a-f]{"+str(n)+"}",value) is not None

def proper_count(value):
    return type(value) is int and value>=0

def validate_s4(earlier):
    if (earlier.get("format")!=S4_FORMAT
        or earlier.get("status")!="PASS_SOURCE_BOUND_CPU_READBACK"
        or earlier.get("counts")!={"total":240,"success":240,"failed":0,"unread":0}
        or earlier.get("exact_original_sources")!=11
        or earlier.get("new_epoch_private_ack")!=S4_ACK
        or earlier.get("new_epoch_sqlite_sha256")!=S4_SQLITE
        or earlier.get("eight_table_remote_restore") is not True
        or earlier.get("old_archive_ref_untouched") is not True
        or earlier.get("previous_private_state_ref_untouched") is not True
        or earlier.get("private_ref_writes")!=0
        or earlier.get("automatic_qualified_supply_demand_adoption") is not False
        or earlier.get("new_model_calls")!=0
        or earlier.get("forecast_accuracy")!="UNVERIFIED"):
        fail("S4_IMMUTABLE_RECEIPT_INTEGRITY")
    rows=earlier.get("source_versions")
    if not isinstance(rows,list) or len(rows)!=11:
        fail("S4_EXACT_SOURCE_COUNT")
    identities=[]
    for item in rows:
        if (not isinstance(item.get("document_id"),str) or not item["document_id"]
            or not all(is_hash(item.get(k),64) for k in ("body_sha256","raw_sha256"))
            or item.get("read_state")!="READ_COMPLETE"
            or item.get("review_state") not in STATES
            or item.get("source_validation")!="EXACT_NATIVE_AND_BODY_HASHES"
            or item.get("target_review_performed") is not True
            or item.get("meaning_analysis_failed") is not False
            or item.get("LIVE_writes")!=0
            or any(not proper_count(item.get(k)) for k in
                   ("source_bound_event_count","graph_independent_pair_count",
                    "strict_independent_pair_count","strict_forecast_candidate_count",
                    "total","success","failed","unread"))
            or item["total"]!=item["success"] or item["unread"]!=0 or item["failed"]!=0):
            fail("S4_SOURCE_OR_SEMANTIC_ROW_NOT_VERIFIED")
        identities.append(tuple(item[k] for k in ("document_id","body_sha256","raw_sha256")))
    if len(set(identities))!=11 or sum(row["total"] for row in rows)!=240:
        fail("S4_SOURCE_VERSION_COLLISION_OR_WINDOW_COUNT")
    review=earlier.get("semantic_review",{})
    if (review.get("exact_source_semantic_reviews")!=11
        or review.get("original_exact_body_validation")!=11
        or review.get("semantic_review_failures")!=0
        or review.get("automatic_LIVE_promotions")!=0
        or any(review.get(key)!=sum(r[part] for r in rows) for key,part in (
            ("source_bound_events","source_bound_event_count"),
            ("graph_independent_pair_count","graph_independent_pair_count"),
            ("strict_independent_pair_count","strict_independent_pair_count"),
            ("strict_forecast_candidate_count","strict_forecast_candidate_count")))
        ):
        # Verify each aggregate against independently counted source rows below.
        fail("S4_SEMANTIC_AGGREGATE_MISMATCH")
    return rows

def triage(earlier, semantic_receipts):
    """Fail closed if any S4 source receipt differs from the private semantic log."""
    source_rows=validate_s4(earlier)
    by_key={}
    for receipt in semantic_receipts:
        key=tuple(receipt.get(k) for k in ("document_id","body_sha256","raw_sha256"))
        if key in by_key: fail("DUPLICATE_SEMANTIC_SOURCE")
        by_key[key]=receipt
    original_keys={tuple(r[k] for k in ("document_id","body_sha256","raw_sha256")) for r in source_rows}
    if set(by_key)!=original_keys:
        fail("MISSING_OR_EXTRA_ORIGINAL_SEMANTIC_RECEIPT")
    result=[];total_events=Counter();missing=Counter();reasons=Counter()
    for row in source_rows:
        identity=tuple(row[k] for k in ("document_id","body_sha256","raw_sha256"))
        receipt=by_key[identity]
        if any(receipt.get(k)!=row.get(k) for k in COMPARED):
            fail("PRIVATE_SEMANTIC_SOURCE_BINDING_CHANGED")
        if any(receipt.get(k)!=row.get("strict_independent_pair_count" if k=="strict_pair_count" else k)
               for k in COUNTS):
            fail("PRIVATE_SEMANTIC_COUNTS_CHANGED")
        events=receipt.get("event_traces")
        pairs=receipt.get("pair_traces")
        fields=receipt.get("missing_fields")
        if (not isinstance(events,list) or not isinstance(pairs,list)
            or not isinstance(fields,list)
            or len(events)!=row["source_bound_event_count"]
            or len(pairs)!=row["graph_independent_pair_count"]
            or any(not isinstance(x,str) or x not in FIELDS for x in fields)
            or len(set(fields))!=len(fields)
            or row["strict_independent_pair_count"]>row["graph_independent_pair_count"]
            or row["strict_forecast_candidate_count"]>row["strict_independent_pair_count"]):
            fail("PRIVATE_SEMANTIC_GRAPH_OR_FIELD_INCONSISTENT")
        seen=set()
        for event in events:
            if not isinstance(event,dict) or event.get("document_id")!=row["document_id"]:
                fail("PRIVATE_GRAPH_EVENT_NOT_SOURCE_BOUND")
            eid=event.get("event_id")
            if not isinstance(eid,str) or not eid or eid in seen:
                fail("PRIVATE_GRAPH_EVENT_ID_DUPLICATE")
            seen.add(eid)
        reason=receipt.get("reason_code")
        if not isinstance(reason,str) or not reason or len(reason)>128 or "\n" in reason:
            fail("UNSUPPORTED_SOURCE_REVIEW_REASON")
        if (reason=="TARGET_FIELDS_UNKNOWN" and not fields
            or reason=="CPU_ENTITY_ONLY_SEMANTICS_PENDING" and events):
            fail("CAUSE_INCONSISTENT_WITH_REAL_SOURCE_EVENTS")
        reasons[reason]+=1
        missing.update(fields)
        total_events["events"]+=len(events)
        total_events["graph_pairs"]+=len(pairs)
        total_events["strict_pairs"]+=row["strict_independent_pair_count"]
        total_events["strict_candidates"]+=row["strict_forecast_candidate_count"]
        result.append({
            "case_sha256":digest(["s5",*identity]), "read_state":"READ_COMPLETE",
            "review_state":row["review_state"],"blocker":reason,
            "missing_fields":sorted(fields),
            "source_bound_events":len(events),
            "graph_independent_pairs":len(pairs),
            "strict_pairs_requires_two_originals":row["strict_independent_pair_count"],
            "actual_eligible_pairs_for_auto_promotion":0,
            "action":RECOMMENDATIONS.get(reason,"SOURCE_BOUND_MANUAL_REVIEW_REQUIRED"),
            "state":"HOLD_NO_AUTOMATIC_PROMOTION"})
    count_check={"events":"source_bound_events","graph_pairs":"graph_independent_pair_count",
                 "strict_pairs":"strict_independent_pair_count",
                 "strict_candidates":"strict_forecast_candidate_count"}
    if any(total_events[a]!=earlier["semantic_review"][b] for a,b in count_check.items()):
        fail("SOURCE_BOUND_COUNTER_TOTALS_MISMATCH")
    report={
        "format":FORMAT,
        "scope":"EXACT_S4_ORIGINAL_11_ONLY_NOT_THE_ENTIRE_RSS_CORPUS",
        "status":"PASS_SOURCE_BOUND_GAP_TRIAGE_AND_NO_FALSE_PROMOTION",
        "session5_goal":"PARTIAL_NO_INDEPENDENT_QUALIFIED_DEMAND_SUPPLY_PAIRS",
        "original_sources":11,
        "original_cpu_windows_verified":240,
        "meaning_reviewed_sources":11,
        "source_bound_events":total_events["events"],
        "observed_graph_independent_pair_diagnostics":total_events["graph_pairs"],
        "observed_strict_pair_diagnostics":total_events["strict_pairs"],
        "independently_original_verified_supply_demand_pairs":0,
        "automatically_promoted_candidates":0,
        "review_state_counts":dict(sorted(Counter(x["review_state"] for x in result).items())),
        "blocker_counts":dict(sorted(reasons.items())),
        "missing_target_field_counts":dict(sorted(missing.items())),
        "evidence_hold_cases":len(result),
        "upstream_epoch_ack":S4_ACK,
        "upstream_sqlite_sha256":S4_SQLITE,
        "private_epoch_writes":0,
        "model_inference_calls":0,
        "public_dashboard_deployment":"NOT_RUN",
        "forecast_accuracy":"UNVERIFIED",
        "next_gate":"ACQUIRE_AND_VERIFY_INDEPENDENT_PRIMARY_DEMAND_AND_QUALIFIED_SUPPLY_ORIGINALS",
        "verified_primary_pair_material":"NOT_AVAILABLE_IN_THIS_SOURCE_SEPARATED_COHORT",
        "research_only":True}
    # If a future result contains a synthetic-looking positive counter, never
    # count it as a verified independent real-world pair without BOTH originals.
    if total_events["strict_pairs"]:
        report["session5_goal"]="BLOCKED_POSITIVE_PAIR_REQUIRES_TWO_VERIFIED_PRIMARY_ORIGINALS"
    return report,result

def write_receipt(directory,report,cases):
    directory=Path(directory)
    if directory.exists():fail("OUTPUT_DIRECTORY_ALREADY_EXISTS")
    directory.mkdir(parents=True)
    dbfile=directory/"s5-cases.sqlite3"
    with sqlite3.connect(dbfile) as db:
        db.execute("CREATE TABLE cases(id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,payload TEXT NOT NULL)")
        for case in cases:
            value=canonical(case)
            db.execute("INSERT INTO cases VALUES (?,?,?)",
                       (case["case_sha256"],digest(value.encode()),value))
    report=dict(report)
    report["cases_sqlite_sha256"]=digest(dbfile.read_bytes())
    report["cases_count"]=len(cases)
    (directory/"s5-summary.json").write_text(canonical(report)+"\n")
    readback(directory)
    return report

def readback(directory):
    directory=Path(directory)
    report=json.loads((directory/"s5-summary.json").read_text())
    dbfile=directory/"s5-cases.sqlite3"
    if report.get("cases_sqlite_sha256")!=digest(dbfile.read_bytes()):
        fail("REQUERY_SQLITE_HASH_MISMATCH")
    with sqlite3.connect(dbfile.resolve().as_uri()+"?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()!=("ok",):
            fail("REQUERY_SQLITE_INTEGRITY")
        rows=db.execute("SELECT id,payload_sha256,payload FROM cases ORDER BY id").fetchall()
    if len(rows)!=report.get("cases_count") or len(rows)!=report.get("original_sources"):
        fail("REQUERY_CASE_COUNT_MISMATCH")
    unique=set();restored=[]
    for row_id,payload_sha,payload in rows:
        if digest(payload.encode())!=payload_sha:fail("REQUERY_CASE_PAYLOAD_MISMATCH")
        case=json.loads(payload)
        if case.get("case_sha256")!=row_id or row_id in unique:
            fail("REQUERY_CASE_ID_MISMATCH")
        unique.add(row_id);restored.append(case)
    if (sum(c["source_bound_events"] for c in restored)!=report["source_bound_events"]
        or sum(c["actual_eligible_pairs_for_auto_promotion"] for c in restored)!=0
        or report["automatically_promoted_candidates"]!=0):
        fail("REQUERY_ACTUAL_COUNTS_CHANGED")
    return {"status":"PASS_S5_SOURCE_FREE_SQLITE_FRESH_READBACK",
            "sources":len(rows),"cases_sqlite_sha256":report["cases_sqlite_sha256"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--s4",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.verify_only:
        print("BCT_S5_READBACK="+canonical(readback(a.out)))
        return
    if not a.s4:fail("PINNED_S4_ARTIFACT_REQUIRED")
    earlier=json.loads(a.s4.read_text())
    validate_s4(earlier)
    import bct_s4_epoch_original_source_readback as s4
    from bct.v4 import cpu_operations as op, cpu_resume as resume, cpu_review
    from bct.objective_lock import stamp_export
    with tempfile.TemporaryDirectory(prefix="bct-s5-readonly-epoch-") as temp:
        home=Path(temp)
        checkpoint=home/"checkpoint";checkpoint.mkdir()
        receipt,_=s4.snapshot_commit(home/"private",S4_ACK,checkpoint)
        restored=op.restore(checkpoint,home/"database")
        if (restored.get("restored") is not True or restored.get("tables")!=8
            or restored.get("sqlite_sha256")!=S4_SQLITE
            or receipt.get("sqlite_sha256")!=S4_SQLITE):
            fail("PRIVATE_EPOCH_REMOTE_RESTORATION_MISMATCH")
        ledger=resume.Ledger(home/"database")
        try:
            resume.audit(ledger)
            keys={tuple(s[k] for k in ("document_id","body_sha256","raw_sha256"))
                  for s in earlier["source_versions"]}
            latest={}
            for kind,payload in ledger.db.execute(
                "SELECT kind,payload FROM events WHERE kind IN "
                "('CPU_ANALYSIS_RESULT','CPU_ANALYSIS_FAILURE') ORDER BY seq"):
                item=json.loads(payload)
                key=tuple(item.get(k) for k in ("document_id","body_sha256","raw_sha256"))
                if key in keys:
                    latest[key]=(kind,item)
            if set(latest)!=keys or any(kind!="CPU_ANALYSIS_RESULT"
                   for kind,item in latest.values()):
                fail("PRIVATE_EXACT_SEMANTIC_RESULT_ABSENT_OR_FAILED")
            for kind,item in latest.values():
                cpu_review.validate_receipt(item)
            cases=[item for _,item in latest.values()]
            if ledger.db.execute("SELECT COUNT(*) FROM firsts").fetchone()!=(0,):
                fail("RESEARCH_FIRSTS_MUST_REMAIN_ZERO")
        finally:
            ledger.close()
    result,cases=triage(earlier,cases)
    final=write_receipt(a.out,stamp_export(result),cases)
    print("BCT_S5_EVIDENCE_GATE="+canonical({
        "status":final["status"],"session5_goal":final["session5_goal"],
        "sources":final["original_sources"],
        "events":final["source_bound_events"],
        "independent_pairs":final["independently_original_verified_supply_demand_pairs"],
        "blockers":final["blocker_counts"],
        "missing_fields":final["missing_target_field_counts"],
        "fresh_readback":"PASS","LIVE_writes":0}))

if __name__=="__main__":
    main()
