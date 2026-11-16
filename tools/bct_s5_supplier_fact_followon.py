"""S5 bounded real public issuer/SEC supply evidence audit (research-only).

Exact public URLs, original body hashes and source-span locators. Distinct
websites or copies of the same earnings announcement are not distinct economic
demand/supply events. Nothing qualifies a customer-specific available kgU.
No private input, model inference, production ranking or LIVE mutation.
"""
import argparse
from collections import Counter,defaultdict
from datetime import date
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

FORMAT="bct-s5-supplier-facts-readonly-v1"
MANIFEST="bct-s5-official-supplier-followon-v1"
CUTOFF="2026-11-16"
UNKNOWN="UNKNOWN"
SOURCE_IDS=frozenset(("centrus_sec_q3_ex99","centrus_issuer_q3","bwxt_antares_issuer"))
PINNED={
 "centrus_sec_q3_ex99":"https://www.sec.gov/Archives/edgar/data/1065059/000162828026070229/ex991-10q2026_11x04.htm",
 "centrus_issuer_q3":"https://centrusenergy.gcs-web.com/news-releases/news-release-details/centrus-reports-third-quarter-2026-results",
 "bwxt_antares_issuer":"https://www.bwxt.com/bwxt-announces-contract-with-antares-for-triso-nuclear-fuel-production/",
}
PRIOR={"run_id":43821707141,"artifact_id":14205155407,
       "artifact_sha256":"6f949e59c47e040d1a555426bc9a1ac345892ebd25d41b5eebdc62e2fdb2c563",
       "workflow_head_sha":"39b1a054ede6020a9d0e15d492a2b7abe7d67d7b"}
FACTS={
 "CENTRUS_2026Q3_SINGLE_DISCLOSURE":(
  ("CENTRUS_EXISTING_CASCADE_16",r"existing\s+16[- ]centrifuge\s+cascade",16,"CENTRIFUGE_COUNT_NOT_CAPACITY_KGU"),
  ("CENTRUS_CONTINGENT_LEU_HALEU_BACKLOG_5_4",r"contingent\s+Low-Enriched\s+Uranium\s*\(LEU\)\s+and\s+High-Assay\s+Low-Enriched\s+Uranium\s*\(HALEU\)\s+enrichment\s+backlog\s+to\s+\$5\.4\s+billion",5.4,"USD_BILLION_NOT_AVAILABLE_HALEU_MTU"),
  ("CENTRUS_FY27_DOE_OPERATION_FUNDING_ABSENT",r"current\s+DOE\s+budget\s+proposed\s+for\s+fiscal\s+year\s+2027\s+does\s+not\s+include\s+further\s+funding\s+for\s+the\s+operation\s+of\s+the\s+HALEU\s+cascade",True,"PROPOSED_BUDGET_RISK_NOT_STOPPED_OPERATION"),
  ("CENTRUS_DOE_NO_FURTHER_OPTIONS_INTENT",r"DOE\s+has\s+communicated\s+that\s+it\s+does\s+not\s+currently\s+intend\s+to\s+exercise\s+further\s+options\s+under\s+the\s+HALEU\s+Operation\s+Contract",True,"CURRENT_OPTION_INTENT_NOT_CANCELLED_CONTRACT"),
  ("CENTRUS_NEW_CENTRIFUGE_SHIPMENT",r"completed\s+manufacturing\s+and\s+began\s+shipping\s+centrifuges",True,"SUPPLY_CHAIN_PROGRESS_NOT_MARKET_DELIVERABLE_KGU"),
 ),
 "ANTARES_BWXT_FUEL_FRAMEWORK":(
  ("BWXT_ANTARES_INITIAL_ALLOCATION_1_MTU",r"initial\s+allocation\s+of\s+1\s+MTU",1,"INITIAL_FRAMEWORK_ALLOCATION_NOT_YEARLY_CUSTOMER_FIRM_TAKE"),
  ("BWXT_ANTARES_FUTURE_TASK_ORDERS",r"future\s+task\s+orders\s+that\s+define\s+specific\s+quantities,\s+delivery\s+schedules\s+and\s+technical\s+requirements",True,"FUTURE_TASK_ORDERS_MISSING_EXACT_FIRM_YEAR_AND_SPEC"),
  ("BWXT_EXISTING_FABRICATION_LINE",r"same\s+TRISO\s+fabrication\s+line\s+used\s+to\s+produce\s+fuel\s+for\s+(?:the\s+Department\s+of\s+War|Antares)",True,"KNOWN_FAB_LINE_NOT_AVAILABLE_UNRESERVED_OUTPUT"),
 )
}
ALL_FACT_IDS={v[0] for rules in FACTS.values() for v in rules}
assert len(ALL_FACT_IDS)==sum(map(len,FACTS.values()))

def canonical(o):
    return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(s):
    return hashlib.sha256(s if isinstance(s,bytes) else s.encode()).hexdigest()
def require(ok,why):
    if not ok: raise ValueError("S5_SUPPLIER_"+why)

def secure(url,host):
    p=urlsplit(url)
    require(p.scheme=="https" and p.hostname==host and not p.username and not p.password
            and not p.query and not p.fragment and p.port is None,"UNVERIFIED_ORIGINAL_URL")
    try: addr=ipaddress.ip_address(host)
    except ValueError:addr=None
    require(addr is None or addr.is_global,"PRIVATE_OR_NONPUBLIC_ADDRESS")
    return url

def validate_manifest(m):
    require(m.get("format")==MANIFEST and m.get("cutoff")==CUTOFF
            and m.get("mode")=="PUBLIC_READ_ONLY_BACKFILL"
            and m.get("target_id")=="unobligated-haleu-us-qualified-supply"
            and m.get("scope")=="ANTARES_TRISO_CUSTOMER_YEARLY_QUANTITY_VS_ELIGIBLE_UNRESERVED_SUPPLY"
            and m.get("public_source_policy")=="FIXED_OFFICIAL_URLS_ONLY_NO_PRIVATE_DERIVED_QUERIES"
            and m.get("previous_q3_proof")==PRIOR,"MANIFEST_OBJECTIVE_OR_PRIOR_CHANGED")
    rows=m.get("sources")
    require(isinstance(rows,list) and len(rows)==3
            and {r.get("id") for r in rows}==SOURCE_IDS,"SOURCE_COHORT_CHANGED")
    for row in rows:
        require(row.get("url")==PINNED[row["id"]],"UNAPPROVED_SOURCE_URL")
        secure(row["url"],row["host"])
        require(row.get("causal_event") in FACTS
                and row.get("date")<=CUTOFF
                and row.get("title") and row.get("issuer_marker")
                and isinstance(row.get("date_markers"),list)
                and 1<=len(row["date_markers"])<=3,"INVALID_OFFICIAL_SOURCE_IDENTITY")
        date.fromisoformat(row["date"])
        require(row["date"]<=CUTOFF,"FUTURE_SOURCE")
    return rows

def validate_prior(s):
    require(s.get("format")=="bct-s5-typed-quantitative-original-check-v1"
            and s.get("target_id")=="unobligated-haleu-us-qualified-supply"
            and s.get("official_originals_fetched")==1
            and s.get("firm_contract_cumulative_MTU_by_2030")==1
            and s.get("Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30")==0.5
            and s.get("Standard_building_envelope_MTU_per_year_not_operational")==5.5
            and s.get("new_early_candidates")==s.get("LIVE_writes")==0
            and s.get("confirmed_shortage")=="NOT_ESTABLISHED"
            and s.get("source_text_exported") is False
            and all(v["same_scope_physical_gap_MTU"]==UNKNOWN
                    for v in s.get("annual_comparison",{}).values())
            and set(s.get("annual_comparison",{}))=={"2027","2028","2029","2030"},
            "PRIOR_Q3_QUANTITATIVE_RECEIPT_MISMATCH")
    return True

class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.exclude=0
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):self.exclude+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript") and self.exclude:self.exclude-=1
    def handle_data(self,data):
        if not self.exclude and data.strip():self.parts.append(data)
    def result(self):
        return " ".join(" ".join(self.parts).split())

def body_text(raw):
    page=Visible();page.feed(raw.decode("utf-8",errors="replace"))
    return page.result()

def source_attested(s,txt):
    if len(txt)<550:return False
    text=txt.casefold()
    if s["issuer_marker"].casefold() not in text:return False
    title=s["title"].casefold()
    starts=[m.start() for m in re.finditer(re.escape(title),text)]
    return any(any(d.casefold() in text[max(0,k-240):k+len(title)+350]
                   for d in s["date_markers"]) for k in starts)

def read_source(s,raw,final=None,error=None):
    case={"source_id":s["id"],"issuer":s["issuer"],"causal_event":s["causal_event"],
          "url":s["url"],"publication_date":s["date"],
          "status":"ACCESS_HOLD","facts":[],"model_calls":0,
          "LIVE_writes":0,"strict_global_provenance":"NOT_INFERRED_FROM_URL",
          "qualified_customer_unreserved_supply_MTU":UNKNOWN}
    if raw is None:
        case["access_failure_type"]=error or "UNKNOWN"
        txt=None
    else:
        require(final==s["url"],"CROSS_SITE_OR_CHANGED_FINAL_URL")
        txt=body_text(raw)
        if not source_attested(s,txt):
            case["status"]="VISIBLE_DATE_ISSUER_HOLD"
        else:
            case["status"]="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY"
        case.update(raw_sha256=digest(raw),visible_sha256=digest(txt),
                    visible_characters=len(txt))
    for fid,pattern,meaning,semantics in FACTS[s["causal_event"]]:
        match=(re.search(pattern,txt,re.I) if txt is not None and
               case["status"]=="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY" else None)
        if match:
            span=txt[match.start():match.end()]
            fact={"fact_id":fid,"state":"VISIBLE_SOURCE_SPAN_HASH_VERIFIED",
                  "value":meaning,"interpretation":semantics,
                  "location":{"start":match.start(),"end":match.end(),
                              "span_sha256":digest(span)}}
        else:
            fact={"fact_id":fid,"state":"HOLD_NOT_PROVEN_FROM_THIS_ORIGINAL",
                  "value":UNKNOWN,"interpretation":semantics,"location":None}
        case["facts"].append(fact)
    return case

def aggregate(m,prior,cases):
    validate_manifest(m);validate_prior(prior)
    require(len(cases)==3 and {c.get("source_id") for c in cases}==SOURCE_IDS,"CASE_IDENTITY_INCOMPLETE")
    ref={r["id"]:r for r in m["sources"]}
    groups=defaultdict(list)
    for c in cases:
        original=ref[c["source_id"]]
        require(all(c.get(k)==original[v] for k,v in
                    (("url","url"),("issuer","issuer"),
                     ("causal_event","causal_event"),
                     ("publication_date","date"))) and
                c.get("model_calls")==c.get("LIVE_writes")==0 and
                c.get("qualified_customer_unreserved_supply_MTU")==UNKNOWN,
                "SOURCE_IDENTITY_OR_SIDE_EFFECT")
        expected={x[0]:x for x in FACTS[c["causal_event"]]}
        require(len(c["facts"])==len(expected)
                and {x["fact_id"] for x in c["facts"]}==set(expected),"SOURCE_FACT_SET_CHANGED")
        for f in c["facts"]:
            e=expected[f["fact_id"]]
            require(f["interpretation"]==e[3]
                    and f["value"] in (UNKNOWN,e[2]),"IMPUTED_OR_WRONG_UNIT")
            if f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED":
                p=f["location"]
                require(c["status"]=="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY"
                        and p and type(p.get("start")) is int and type(p.get("end")) is int
                        and p["start"]>=0 and p["end"]>p["start"]
                        and re.fullmatch("[0-9a-f]{64}",p.get("span_sha256","")),
                        "UNVERIFIED_SOURCE_LOCATOR")
            else:
                require(f["state"]=="HOLD_NOT_PROVEN_FROM_THIS_ORIGINAL"
                        and f["value"]==UNKNOWN and f["location"] is None,
                        "UNSUPPORTED_FACT_STATE")
        groups[c["causal_event"]].append(c)
    centrus=groups["CENTRUS_2026Q3_SINGLE_DISCLOSURE"]
    bwxt=groups["ANTARES_BWXT_FUEL_FRAMEWORK"]
    require(len(centrus)==2 and len(bwxt)==1,"DISTINCT_ECONOMIC_EVENT_SET_CHANGED")
    verified={f["fact_id"] for c in cases for f in c["facts"]
              if f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED"}
    valid_centrus={f["fact_id"] for c in centrus for f in c["facts"]
                   if f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED"}
    valid_bwxt={f["fact_id"] for c in bwxt for f in c["facts"]
                if f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED"}
    # 2 reports of the same Centrus Q3 event remain only 1 issuer/event.
    return {
      "format":FORMAT,"scope":"PUBLIC_PINNED_SUPPLIER_ALTERNATIVE_AND_RISK_EVIDENCE",
      "status":"PASS_READONLY_SOURCE_BOUND_RISK_AND_NONPROMOTION_CLASSIFICATION",
      "session5_final":"PARTIAL_NO_SAME_PERIOD_ELIGIBLE_UNRESERVED_SUPPLY_EVIDENCE",
      "primary_urls_attempted":len(cases),
      "public_source_bodies_captured":sum(c.get("raw_sha256") is not None for c in cases),
      "verified_visible_public_originals":sum(c["status"]=="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY" for c in cases),
      "source_holds":sum(c["status"]!="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY" for c in cases),
      "distinct_issuer_economic_events_with_evidence":int(bool(valid_centrus))+int(bool(valid_bwxt)),
      "centrus_same_disclosure_copies_not_independent_pair":len(centrus),
      "centrus_bound_fact_ids":sorted(valid_centrus),
      "bwxt_bound_fact_ids":sorted(valid_bwxt),
      "verified_distinct_fact_ids":sorted(verified),
      "verified_distinct_fact_count":len(verified),
      "centrus_cascade_machine_count":16 if "CENTRUS_EXISTING_CASCADE_16" in valid_centrus else UNKNOWN,
      "centrus_contingent_backlog_usd_billion":5.4 if "CENTRUS_CONTINGENT_LEU_HALEU_BACKLOG_5_4" in valid_centrus else UNKNOWN,
      "centrus_fy2027_budget_operation_funding_not_included":
          True if "CENTRUS_FY27_DOE_OPERATION_FUNDING_ABSENT" in valid_centrus else UNKNOWN,
      "centrus_D​OE_further_options_not_planned":
          True if "CENTRUS_DOE_NO_FURTHER_OPTIONS_INTENT" in valid_centrus else UNKNOWN,
      "bwxt_initial_contract_allocation_MTU_not_annual":
          1 if "BWXT_ANTARES_INITIAL_ALLOCATION_1_MTU" in valid_bwxt else UNKNOWN,
      "bwxt_future_task_orders_required":
          True if "BWXT_ANTARES_FUTURE_TASK_ORDERS" in valid_bwxt else UNKNOWN,
      "2027_2030_customer_firm_annual_delivery_MTU":{str(y):UNKNOWN for y in range(2027,2031)},
      "2027_2030_customer_eligible_unreserved_TRISO_output_MTU":{str(y):UNKNOWN for y in range(2027,2031)},
      "2027_2030_demonstrated_demand_minus_supply_MTU":{str(y):UNKNOWN for y in range(2027,2031)},
      "strict_pair_evaluated":False,"actual_qualified_pair_count":"NOT_EVALUATED",
      "new_bottleneck_candidates":0,"model_API_calls":0,
      "private_epoch_writes":0,"LIVE_writes":0,"dashboard_deployed":False,
      "original_source_text_stored":False,
      "prior_S5_Q3_receipt_reused":True,
      "next_required_evidence":[
        "CUSTOMER_SIGNED_YEARLY_TRISO_TASK_ORDERS_WITH_ASSAY_AND_DELIVERY_WINDOW",
        "FIRM_VS_OPTION_FABRICATOR_ALLOCATIONS_DEDUPLICATED_BY_REACTOR",
        "CUSTOMER_QUALIFIED_UNRESERVED_ACCEPTED_PHYSICAL_SUPPLY_BY_YEAR",
        "HALEU_ENRICHMENT_FEED_DISTINGUISHED_FROM_FABRICATED_TRISO_FUEL",
        "RIVAL_BWXT_CAPACITY_AND_RESERVED_OTHER_CUSTOMERS",
        "DOE_OPERATION_FUNDING_RISK_NOT_MISREAD_AS_CURRENT_ZERO_SUPPLY"
      ],
      "forecast_accuracy":"UNVERIFIED"}
def persist(folder,report,cases):
    folder=Path(folder)
    require(not folder.exists(),"NO_OVERWRITE")
    folder.mkdir(parents=True)
    dbpath=folder/"source-free.sqlite3"
    with sqlite3.connect(dbpath) as c:
        c.execute("CREATE TABLE cases(id TEXT PRIMARY KEY,hash TEXT NOT NULL,record TEXT NOT NULL)")
        for x in sorted(cases,key=lambda z:z["source_id"]):
            payload=canonical(x)
            c.execute("INSERT INTO cases VALUES(?,?,?)",
                      (x["source_id"],digest(payload),payload))
    output=dict(report)
    output["sql_sha256"]=digest(dbpath.read_bytes())
    (folder/"summary.json").write_text(canonical(output)+"\n")
    requery(folder)
    return output
def requery(folder):
    folder=Path(folder)
    report=json.loads((folder/"summary.json").read_text())
    dbpath=folder/"source-free.sqlite3"
    require(digest(dbpath.read_bytes())==report.get("sql_sha256"),"SQLITE_SHA_CHANGED")
    with sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro",uri=True) as conn:
        require(conn.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INTEGRITY")
        rows=conn.execute("SELECT id,hash,record FROM cases ORDER BY id").fetchall()
    require(len(rows)==3,"REQUERY_SOURCE_COUNT")
    cases=[]
    for sid,hashvalue,payload in rows:
        require(digest(payload)==hashvalue,"REQUERY_PAYLOAD_HASH")
        v=json.loads(payload)
        require(v["source_id"]==sid and not set(v).intersection(
               ("body","raw","source_quote","article_html","secret","document_text")),
               "REQUERY_PRIVATE_CONTENT_OR_ID")
        cases.append(v)
    require(report["LIVE_writes"]==report["model_API_calls"]==report["private_epoch_writes"]==0
            and report["new_bottleneck_candidates"]==0 and
            report["strict_pair_evaluated"] is False and
            all(v==UNKNOWN for v in report["2027_2030_demonstrated_demand_minus_supply_MTU"].values()),
            "REQUERY_FALSE_SHORTAGE_OR_LIVE")
    return {"status":"PASS_FRESH_PROCESS_SOURCE_FREE_REQUERY",
            "cases":len(cases),
            "body_count":report["public_source_bodies_captured"],
            "fact_count":report["verified_distinct_fact_count"]}
def run(args):
    from bct import target_acquisition as fetcher
    from bct.objective_lock import stamp_export
    manifest=json.loads(args.manifest.read_text())
    rows=validate_manifest(manifest)
    prior=json.loads(args.prior.read_text())
    validate_prior(prior)
    items=[]
    for s in rows:
        try:
            raw,final,http,ctype=fetcher.fetch(s["url"])
            require(http==200 and "html" in ctype.lower(),"NO_VALID_HTML_200")
            item=read_source(s,raw,final=final)
        except Exception as e:
            item=read_source(s,None,error=(("HTTP_"+str(e.code)) if hasattr(e,"code")
                                           else type(e).__name__))
        items.append(item)
        print("S5_SUPPLIER_SOURCE="+canonical({
              "id":item["source_id"],"status":item["status"],
              "bound_facts":sum(f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED" for f in item["facts"]),
              "held_facts":sum(f["value"]==UNKNOWN for f in item["facts"]),
              "access_error_type":item.get("access_failure_type","NONE")}),flush=True)
    report=stamp_export(aggregate(manifest,prior,items))
    saved=persist(args.output,report,items)
    print("S5_SUPPLIER_EVIDENCE="+canonical({
          "status":saved["status"],"source_bodies":saved["public_source_bodies_captured"],
          "verified_originals":saved["verified_visible_public_originals"],
          "distinct_facts":saved["verified_distinct_fact_count"],
          "centrus_16_machines":saved["centrus_cascade_machine_count"],
          "fy27_DOE_budget_risk":saved["centrus_fy2027_budget_operation_funding_not_included"],
          "BWXT_task_orders_required":saved["bwxt_future_task_orders_required"],
          "annual_customer_gap":UNKNOWN,
          "strict_pair_evaluated":False,"LIVE_writes":0}),flush=True)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path)
    p.add_argument("--prior",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        print("S5_SUPPLIER_REQUERY="+canonical(requery(args.output)));return
    require(args.manifest is not None and args.prior is not None,"PRIOR_AND_MANIFEST_REQUIRED")
    run(args)
if __name__=="__main__":
    main()
