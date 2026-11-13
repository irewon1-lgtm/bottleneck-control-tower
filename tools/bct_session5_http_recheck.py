#!/usr/bin/env python3
"""Selective Session 5 repair: re-evaluate exactly 9 legacy HTTP articles.

Old full-302 source observations are never discarded. Only previously failed
input-validation URLs are contacted again. The result is a versioned
reconciliation receipt, not a rewritten historical GitHub artifact.
"""
from __future__ import annotations
from collections import Counter
import csv
import json
from pathlib import Path
import argparse

from tools.bct_session5_source_probe import read_packets,run

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def eligible(previous, blind):
    blind_by_id={x["document_id"]:x for x in blind}
    if len(previous)!=302 or len({x["document_id"] for x in previous})!=302:
        raise ValueError("PREVIOUS_302_NOT_UNIQUE")
    hold=[]
    for x in previous:
        ident=x["document_id"];candidate=blind_by_id.get(ident)
        if candidate is None or x["source_url"]!=candidate["url"]:
            raise ValueError("PREVIOUS_ORIGINAL_SOURCE_NOT_MATCHED")
        # Only the known misclassification; original HTTP 403 etc are NOT
        # retried, so publisher boundaries are respected.
        if (x["pilot_status"]=="ACCESS_OR_EXTRACTION_ERROR"
            and x["access_classification"]=="COLLECTOR_ERROR"
            and x.get("error_type")=="ValueError"
            and x["source_url"].startswith("http://")
            and x.get("body_sha256")):
            hold.append(candidate)
    if len(hold)!=9:
        raise ValueError(f"EXPECT_EXACT_9_HTTP_PARSER_MISCLASSIFICATIONS_GOT_{len(hold)}")
    return hold

def write_rows(path, rows, fieldnames):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction="ignore")
        w.writeheader()
        for row in rows:
            values={}
            for k in fieldnames:
                v=row.get(k,"")
                t="|".join(str(x) for x in v) if isinstance(v,list) else "" if v is None else str(v)
                values[k]="'" + t if t.lstrip().startswith(("=","+","-","@","\t","\r")) else t
            w.writerow(values)

def reconcile(old_rows, new_rows, *, expected_ids):
    old={r["document_id"]:dict(r) for r in old_rows}
    new={r["document_id"]:dict(r) for r in new_rows}
    if set(new)!=set(expected_ids) or len(new)!=9:
        raise ValueError("TARGETED_RECHECK_REQUIRES_9")
    for ident in new:
        row=new[ident]
        row["rechecked_in_session5"]="true"
        old[ident].update(row)
    if len(old)!=302:
        raise ValueError("NO_ORIGINAL_302")
    merged=[old[k] for k in sorted(old)]
    counts=Counter(r.get("pilot_status","UNKNOWN") for r in merged)
    if sum(counts.values())!=302 or any(str(r.get("S1_S2_S3","False")).lower()=="true" for r in merged):
        raise ValueError("UNVERIFIED_PROMOTION_OR_COUNT_CHANGE")
    return merged,counts

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--previous",required=True,type=Path)
    p.add_argument("--blind",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    old=read_csv(args.previous)
    blind=read_packets(args.blind)
    target=eligible(old,blind)
    sample=run(target,workers=3)
    merged,counts=reconcile(old,sample["records"],expected_ids=[x["document_id"] for x in target])
    args.output.mkdir(parents=True,exist_ok=True)
    fields=["document_id","source_host","source_url","pilot_status","body_status","body_chars",
        "body_sha256","raw_sha256","provenance_verified","provenance_blockers",
        "access_classification","access_state","error_type","demand_leads","supply_leads",
        "relief_leads","semantic_product_bound_leads","semantic_unknown_product_leads",
        "semantic_conditional_leads","strict_scope_supply_pool",
        "baseline_body_screening_paths","S1_S2_S3","labels","rechecked_in_session5"]
    write_rows(args.output/"merged_302_status.csv",merged,fields)
    write_rows(args.output/"targeted_9_recheck.csv",sample["records"],fields)
    receipt={
        "version":"bct-session5-http-recheck-1",
        "immutable_original_run":43340338148,
        "immutable_original_artifact":13998594561,
        "source_blind_run":43337864700,
        "original_size":302,"rechecked_exact_ids":9,
        "unchanged_originals":293,
        "new_public_HTTP_attempts_max":9,
        "source_documents_now":len(merged),
        "rechecked_status_counts":sample["outcome_counts"],
        "combined_status_counts":dict(counts),
        "original_s3_candidate_promotions":0,"new_s3_candidate_promotions":0,
        "source_full_bodies_redistributed":False,
        "blind_labels_mutated":False,
        "failure_classification_corrected":True,
        "accuracy_status":"NOT_MEASURED_NO_INDEPENDENT_LABELS",
        "source_data_written":False,
    }
    (args.output/"reconcile_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("BCT_SESSION5_HTTP_RECONCILE="+json.dumps(receipt,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
