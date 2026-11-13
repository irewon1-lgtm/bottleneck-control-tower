#!/usr/bin/env python3
"""Source-safe bounded session5 shadow experiment against 302 unseen URLs.

No existing historical AI label, baseline candidate stage, stored article body,
or public operating DB is overwritten. Only body hashes and statistics leave
the runner. Source access is normal HTTPS, one attempt per URL, no bypass.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from bct.future_bottleneck import fetch_capture,screen
from bct.future_body import access_failure,extract_document
from bct.target_acquisition import verify
from bct.future_semantic_shadow import analyze,public_receipt,VERSION

def stamp():
    return datetime.now(timezone.utc).isoformat()

def sha(value):
    return hashlib.sha256(value).hexdigest()

def read_packets(folder):
    rows=[]
    for name in ("blind_reference_packet_240.csv","blind_new_P1_packet.csv"):
        with (folder/name).open(newline="",encoding="utf-8-sig") as f:
            data=list(csv.DictReader(f))
        if name.startswith("blind_reference") and len(data)!=240:
            raise ValueError("BLIND240_EXPECTED")
        if name.startswith("blind_new_P1") and len(data)!=63:
            raise ValueError("BLIND_P1_63_EXPECTED")
        for record in data:
            if (not record.get("document_id") or not record.get("url") or
                    any(record.get(f"{s}_label")!="UNKNOWN" for s in ("DEMAND","SUPPLY","RELIEF"))):
                raise ValueError("BLIND_INPUT_UNVERIFIED")
            rows.append(record)
    by_id={}
    duplicate_urls=set()
    for r in rows:
        old=by_id.get(r["document_id"])
        if old and (old["url"]!=r["url"] or old["source"]!=r["source"]):
            raise ValueError("BLIND_DUPLICATE_ID_VERSION_CONFLICT")
        if old:duplicate_urls.add(r["document_id"])
        by_id[r["document_id"]]=r
    if len(by_id)!=302 or len(duplicate_urls)!=1:
        raise ValueError("BLIND_PACKET_UNIQUE_302_EXPECTED")
    return sorted(by_id.values(), key=lambda r:hashlib.sha256(r["document_id"].encode()).hexdigest())

def status_for(record):
    if record.get("provenance_verified") and record.get("body_status")=="FULL":
        return "VERIFIED_FULL"
    if record.get("body_status")=="FULL":
        return "FULL_UNVERIFIED_ORIGINAL"
    if record.get("body_status")=="PARTIAL":
        return "PARTIAL_ORIGINAL"
    return "UNAVAILABLE_OR_FAILED"

def one_source(row, host_locks):
    url=row["url"];host=urlsplit(url).hostname or ""
    record={"document_id":row["document_id"],"source_host":host,
        "source_url":url,"pilot_status":"NOT_RUN","body_status":"UNAVAILABLE",
        "provenance_verified":False,"body_chars":0,"body_sha256":None,
        "raw_sha256":None,"engine":VERSION,
        "demand_leads":0,"supply_leads":0,"relief_leads":0,
        "semantic_product_bound_leads":0,"semantic_unknown_product_leads":0,
        "semantic_conditional_leads":0,"strict_scope_supply_pool":0,
        "baseline_body_screening_paths":[],
        "S1_S2_S3":False,"labels":"UNKNOWN","source_version_hash_exists":False}
    try:
        if not host:
            raise ValueError("MISSING_PUBLISHER_HOST")
        # Avoid concurrent requests to the same publisher; never circumvent
        # an access challenge or paywall by impersonation/proxies/retries.
        with host_locks[host]:
            fetched=fetch_capture(url)
        extraction=extract_document(fetched["html"],http_status=fetched["status"],
                                    content_type=fetched["content_type"])
        status=extraction["body_status"]
        if fetched["truncated"] and status=="FULL":
            status="PARTIAL"
        body=extraction["body"]
        record.update(body_status=status,
                      body_chars=len(body),
                      body_sha256=sha(body.encode()) if body else None,
                      raw_sha256=sha(fetched["raw"]),
                      source_version_hash_exists=bool(body),
                      extraction_method=extraction["extraction_method"],
                      extraction_reasons=extraction["reasons"],
                      access_classification="HTTP_200" if fetched["status"]==200 else "HTTP_NON_200")
        if body and fetched["status"]==200:
            try:
                proof=verify(fetched["raw"],url,fetched["final_url"],stamp(),
                             fetched["status"],fetched["content_type"])
                verified=proof.get("provenance_verified") is True and not fetched["truncated"]
                blockers=proof.get("provenance_blockers") or []
            except Exception as e:
                verified=False;blockers=["PROOF_EXCEPTION_"+type(e).__name__]
            record.update(provenance_verified=verified,provenance_blockers=blockers)
            previous=screen(body)
            semantic=analyze(body,document_id=row["document_id"],origin_url=url,
                prior_screening=previous,body_status=status,provenance_verified=verified)
            receipt=public_receipt(semantic)
            for k,field in [("demand_leads","DEMAND"),("supply_leads","SUPPLY"),("relief_leads","RELIEF")]:
                record[k]=receipt["literal_lead_counts"][field]
            record.update(
                semantic_product_bound_leads=receipt["literal_leads_count"]-receipt["unknown_product_leads"],
                semantic_unknown_product_leads=receipt["unknown_product_leads"],
                semantic_conditional_leads=sum(x["source_language_status"]=="CONDITIONAL_OR_NEGATED"
                                               for x in semantic["literal_leads"]),
                strict_scope_supply_pool=sum(x["supply_pool"]!="UNKNOWN" for x in semantic["literal_leads"]),
                baseline_body_screening_paths=previous["discovery_paths"],
                S1_S2_S3=semantic["S1_S2_S3_assigned"],
                source_text_published=False)
        record["pilot_status"]=status_for(record)
    except Exception as e:
        diagnostic=access_failure(e)
        record.update(pilot_status="ACCESS_OR_EXTRACTION_ERROR",error_type=type(e).__name__,
                      access_classification=diagnostic["category"],
                      access_state=diagnostic["state"],
                      retryable=diagnostic.get("retryable",False))
    return record

def run(rows, *, workers=6):
    if not 1<=workers<=6:
        raise ValueError("MAX_CONCURRENCY_6")
    hosts=sorted({urlsplit(r["url"]).hostname for r in rows})
    locks={h:threading.Lock() for h in hosts}
    outcomes=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        tasks={executor.submit(one_source,row,locks):row["document_id"] for row in rows}
        for task in as_completed(tasks):
            try:outcomes.append(task.result())
            except Exception as e:
                # Full batch continues while exceptions stay visible.
                outcomes.append({"document_id":tasks[task],"pilot_status":"TASK_EXCEPTION",
                                 "error_type":type(e).__name__,"labels":"UNKNOWN",
                                 "S1_S2_S3":False})
            if len(outcomes)%25==0:
                print(json.dumps({"processed":len(outcomes),"total":len(rows),
                    "verified_full":sum(x.get("pilot_status")=="VERIFIED_FULL" for x in outcomes),
                    "complete":False}),flush=True)
    outcomes.sort(key=lambda x:x["document_id"])
    counts=Counter(x.get("pilot_status","UNKNOWN") for x in outcomes)
    classified=Counter(x.get("access_classification","UNKNOWN") for x in outcomes)
    source_hosts=Counter(x.get("source_host","UNKNOWN") for x in outcomes)
    return {"schema":"bct-session5-readonly-302-source-shadow-v1",
        "as_of":stamp(),"status":"PASS_ATTEMPTED_ALL_302_IF_COUNTS_MATCH",
        "attempted":len(outcomes),"unique_ids":len({x["document_id"] for x in outcomes}),
        "source_count":len(source_hosts),"outcome_counts":dict(counts),
        "access_classes":dict(classified),
        "prior_full_body_not_duplicated":True,
        "source_titles_and_raw_bodies_retained":False,
        "meaningful_source_checked":sum(bool(x.get("body_sha256")) for x in outcomes),
        "verified_full":counts["VERIFIED_FULL"],
        "extracted_full_unverified":counts["FULL_UNVERIFIED_ORIGINAL"],
        "candidate_signal_counts":{k:sum(x.get(k,0)>0 for x in outcomes)
            for k in ("demand_leads","supply_leads","relief_leads")},
        "source_bound_product_documents":sum(x.get("semantic_product_bound_leads",0)>0 for x in outcomes),
        "unknown_product_documents":sum(x.get("semantic_unknown_product_leads",0)>0 for x in outcomes),
        "AI_model_calls":0,"external_paid_requests":0,"source_HTTP_requests_max":len(rows),
        "publisher_login_bypass":0,"source_database_writes":0,
        "S_stages_promoted":sum(x.get("S1_S2_S3") is True for x in outcomes),
        "accuracy_status":"NOT_MEASURED_NO_INDEPENDENT_BLIND_LABELS",
        "old_reference_labels_read":False,
        "records":outcomes}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--blinded",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--workers",type=int,default=6)
    args=p.parse_args()
    rows=read_packets(args.blinded)
    result=run(rows,workers=args.workers)
    if result["unique_ids"]!=302 or result["attempted"]!=302 or result["S_stages_promoted"]!=0:
        raise ValueError("SESSION5_COMPLETENESS_OR_PROMOTION_FAILURE")
    args.output.mkdir(parents=True,exist_ok=True)
    # Metadata evidence contains no third-party body text or publisher cookies.
    (args.output/"source_probe_summary.json").write_text(
        json.dumps({k:v for k,v in result.items() if k!="records"},ensure_ascii=False,indent=2)+"\n")
    with (args.output/"source_probe_by_article.csv").open("w",newline="",encoding="utf-8-sig") as fp:
        fields=["document_id","source_host","source_url","pilot_status","body_status","body_chars",
            "body_sha256","raw_sha256","provenance_verified","provenance_blockers",
            "access_classification","access_state","error_type",
            "demand_leads","supply_leads","relief_leads",
            "semantic_product_bound_leads","semantic_unknown_product_leads",
            "semantic_conditional_leads","strict_scope_supply_pool",
            "baseline_body_screening_paths","S1_S2_S3","labels"]
        w=csv.DictWriter(fp,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        for r in result["records"]:
            safe={k:"|".join(r[k]) if isinstance(r.get(k),list)
                else ("" if r.get(k) is None else str(r[k])) for k in fields}
            for key,value in safe.items():
                if value.lstrip().startswith(("=","+","-","@","\t","\r")):
                    safe[key]="'"+value
            w.writerow(safe)
    print("BCT_SESSION5_SOURCE_PROBE="+json.dumps({k:v for k,v in result.items() if k!="records"},
          ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
