#!/usr/bin/env python3
"""Build a bounded real CPU-run document-id selection from current local snapshots.

The existing future_bottleneck.run still owns acquisition, retries, evidence,
CAS publication and the S-stage guard. This module only chooses which due IDs
to supply with its existing --document-id option. It writes no source DB.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
from tools.bct_session7_queue_monitor import reconcile

MAX_SELECTED=300
MAX_HOST=6


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selection(db_path, sidecar_path, *, budget=300, at=None):
    if not 1<=budget<=MAX_SELECTED:raise ValueError("S7_SELECTION_BUDGET_EXCEEDED")
    before_hash=sha(db_path)
    with sqlite3.connect("file:"+str(Path(db_path).resolve())+"?mode=ro&immutable=1",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("S7_CANONICAL_DB_NOT_INTEGRAL")
        db.row_factory=sqlite3.Row
        rows=[dict(x) for x in db.execute(
            "SELECT id,source,url,title,snippet,published_at,collected_at,updated_at "
            "FROM radar_items WHERE status='active' ORDER BY collected_at,id")]
    if not rows:raise ValueError("S7_ZERO_RSS_SOURCE")
    raw=Path(sidecar_path).read_bytes()
    state=json.loads(raw)
    if not isinstance(state.get("results"),dict):
        raise ValueError("S7_SIDECAR_RESULTS_MISSING")
    at=at or datetime.now(timezone.utc)
    ledger,picks,metrics=reconcile(rows,state["results"],at,budget=budget)
    if sha(db_path)!=before_hash or hashlib.sha256(Path(sidecar_path).read_bytes()).digest()!=hashlib.sha256(raw).digest():
        raise ValueError("S7_SOURCE_GENERATION_CHANGED_DURING_SELECTION")
    if len(picks)>budget or len({r["article_id"] for r in picks})!=len(picks):
        raise ValueError("S7_SELECTED_IDS_NOT_UNIQUE_OR_BOUNDED")
    if any(p["work_action"]!="FETCH_OR_RECHECK_ORIGINAL" or
           p["independent_supply_demand_pair_verified"] is not False or
           p["S1_S2_S3_verified_from_this_run"] is not False
           for p in picks):
        raise ValueError("S7_UNQUALIFIED_EVIDENCE_IN_PLAN")
    return {
      "schema":"bct-session7-real-run-id-selection-v1",
      "selection_only_not_processing_completed":True,
      "created_at_utc":at.isoformat(),
      "db_sha256":before_hash,
      "sidecar_snapshot_sha256":hashlib.sha256(raw).hexdigest(),
      "article_total":len(ledger),
      "previous_sidecar_results":len(state["results"]),
      "unlinked":metrics["articles_without_sidecar"],
      "source_safe_fetch_due":metrics["waiting_fetch_or_recheck"],
      "held_or_deferred":metrics["blocked_or_deferred"],
      "selected_count":len(picks),
      "selected_recent":metrics["selected_recent"],
      "selected_old":metrics["selected_older"],
      "selection_limit":budget,
      "missing_scope_not_a_negative":True,
      "paid_AI_requests":0,
      "source_access_requests":0,
      "verified_bottleneck_promotions":0,
      "ids":[p["article_id"] for p in picks],
      "selected":[{"article_id":p["article_id"],
                   "metadata_priority":p["metadata_priority"],
                   "review_lane":p["review_lane"],
                   "recency_bucket":p["recency_bucket"],
                   "source":p["source"],
                   "work_action":p["work_action"]} for p in picks]
    }


def save_selection(result,output):
    output=Path(output)
    # Important: only validated ID strings are accepted by the shell bridge;
    # no publisher-provided shell text or URL becomes a CLI argument.
    import re
    ids=result["ids"]
    if any(not isinstance(id,str) or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._:-]{0,150}",id) for id in ids):
        raise ValueError("S7_SHELL_ID_NOT_SAFE")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    output.with_suffix(".ids").write_text("\n".join(ids)+("\n" if ids else ""),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--sidecar",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--budget",type=int,default=300)
    args=parser.parse_args()
    obj=selection(args.db,args.sidecar,budget=args.budget)
    save_selection(obj,args.output)
    print("BCT_S7_SELECT_WORK="+json.dumps({key:value for key,value in obj.items() if key not in ("ids","selected")},sort_keys=True),flush=True)


if __name__=="__main__":main()
