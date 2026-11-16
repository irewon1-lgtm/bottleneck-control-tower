"""BCT S5: read-only source-bound physical demand versus installed capacity preflight.

Only fixed PUBLIC official issuer URLs. No original/private text stored in results.
This does not run a strict EARLY engine, score candidates, or change LIVE state.
"""
import argparse
from datetime import datetime,timezone,date
from html.parser import HTMLParser
from html import unescape
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

FORMAT="bct-s5-typed-quantitative-original-check-v1"
MANIFEST_FORMAT="bct-s5-quantitative-primary-20261116-v1"
TARGET="unobligated-haleu-us-qualified-supply"
AS_OF="2026-11-16"
UNKNOWN="UNKNOWN"
PERIODS=("2027","2028","2029","2030")
SOURCE_IDS=frozenset(("standard_2026q3_sec_10q","centrus_2026q3_issuer"))
PRIOR_S5_RUN=43815790180
PRIOR_S5_ARTIFACT=14202675339
PRIOR_S5_SHA="410c4725c3a9ff9426813b8a839f8cc15c0cc494"
PRIOR_S5_DIGEST="sha256:a5b6db4373d060f933fb77e5cbad44ba67cc065f4f1618a98622367b7484b5b4"
# Each fixed section anchor prevents matching numbers in unrelated financial tables.
# evidence is kept only as an offset + SHA of a matched *public* source span.
FACTS={
 "standard_2026q3_sec_10q":[
  ("STDN_FIRM_FABRICATION_TOTAL_MTU",1,"MTU_FABRICATED_TRISO",
   "FIRM_MULTIYEAR_CONTRACT_NOT_ANNUAL_ORDER","On August 26, 2026",
   r"Antares Nuclear.{0,270}one MTU\s*\(\s*1,000\s*kgU\s*\)",1700),
  ("STDN_OPTION_NOT_COMMITTED_MTU",7,"MTU_FABRICATED_TRISO",
   "CUSTOMER_OPTION_NOT_FIRM","On August 26, 2026",
   r"option for Antares to purchase up to seven additional MTU\s*\(\s*7,000\s*kgU\s*\)",1700),
  ("STDN_FIRM_DELIVERY_LATEST","2030-12-31","ISO_DATE",
   "CUMULATIVE_DEADLINE_NOT_ANNUAL_DEMAND","On August 26, 2026",
   r"required to take delivery of the firm quantity by December 31, 2030",1700),
  ("STDN_OPTION_EXERCISE_LATEST","2027-12-31","ISO_DATE",
   "OPTION_EXERCISE_NOT_CONFIRMED_DEMAND","On August 26, 2026",
   r"option is exercisable in one MTU increments by written notice no later than December 31, 2027",1700),
  ("STDN_OPTION_EARLIEST_POSSIBLE_DELIVERY","2028","YEAR",
   "POSSIBLE_NOT_CONTRACTED","On August 26, 2026",
   r"deliveries of exercised quantities beginning as early as 2028",1700),
  ("STDN_INSTALLED_AUTHORIZED_THROUGHPUT_MTU_Y",0.5,"MTU_FABRICATED_TRISO_PER_YEAR",
   "OPERATIONAL_MODULE_RATE_NOT_UNRESERVED_SUPPLY","The table below details our Production Capacity",
   r"Module Throughput Capacity\s*0\.5\s*MTU\s*/\s*y",1600),
  ("STDN_BUILDING_THEORETICAL_MTU_Y",5.5,"MTU_FABRICATED_TRISO_PER_YEAR",
   "BUILDING_FOOTPRINT_NOT_INSTALLED","The table below details our Production Capacity",
   r"Building Throughput Capacity\s*5\.5\s*MTU\s*/\s*y",1600),
  ("STDN_OVERALL_PROCESS_YIELD_PERCENT",63.3,"PERCENT",
   "ALREADY_REFLECTED_IN_REPORTED_THROUGHPUT_NO_DOUBLE_MULTIPLY",
   "The table below details our Production Capacity",
   r"Process Yield\s*%\s*63\.3",1600),
  ("STDN_SN0_REALIZED_UTILIZATION_OVER_PERCENT",25,"PERCENT_LOWER_BOUND",
   "UTILIZATION_OBSERVATION_NOT_CUSTOMER_AVAILABLE_CAPACITY",
   "The Company’s SN-0 facility",r"operates at just above 25%",900),
  ("STDN_FACILITY_APPROVAL_TARGET","2027-02","YEAR_MONTH",
   "REGULATORY_TARGET_NOT_GRANTED_AUTHORIZATION",
   "The Company’s SN-0 facility",
   r"targets receiving DOE authorization to operate at both SN-TN and SN-ID in February 2027",2800),
  ("STDN_FEEDSTOCK_RECEIPT_DEPENDENCY","VERIFIED","QUALITATIVE",
   "FUEL_FEED_SUPPLY_DEPENDENT_NO_MEASURED_RESIDUAL",
   "Feedstock availability",r"ability to perform under customer arrangements depends in part on the availability and timely receipt of enriched uranium feedstock",700),
  ("STDN_LICENSED_BUT_NOT_OPERATING_JV","VERIFIED","QUALITATIVE",
   "APPROVAL_FOR_FUTURE_FABRICATION_NOT_IMMEDIATE_FREE_CAPACITY",
   "Richland SN-F",r"initial capacity of approximately one MTU annually",7000),
 ],
 "centrus_2026q3_issuer":[
  ("CENTRUS_OPERATING_CASCADE_COUNT",16,"CENTRIFUGES",
   "MACHINE_COUNT_NOT_KGU_PER_YEAR","Centrus Reports Third Quarter 2026 Results",
   r"(?:commercial market from existing|commercial market from its existing)\s*16[- ]centrifuge cascade",2500),
  ("CENTRUS_CONTINGENT_BACKLOG_BN_USD",5.4,"USD_BILLION",
   "FINANCIAL_BACKLOG_NOT_PHYSICAL_AVAILABLE_HALEU","Centrus Reports Third Quarter 2026 Results",
   r"contingent.{0,130}enrichment backlog to\s*\$5\.4 billion",2600),
  ("CENTRUS_FY27_DOE_CASCADE_OPTION_RISK","VERIFIED","QUALITATIVE",
   "DOE_PROPOSED_FUNDING_NOT_CONFIRMED_CUSTOMER_CAPACITY","Backlog",
   r"current DOE budget proposed for fiscal year 2027 does not include further funding for the operation of the HALEU cascade",7200),
 ],
}
PINNED_FACT_IDS={row[0] for facts in FACTS.values() for row in facts}
assert len(PINNED_FACT_IDS)==sum(len(v) for v in FACTS.values())

def canon(o):
    return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def sha(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode("utf-8")).hexdigest()
def require(yes,reason):
    if not yes:raise ValueError("BCT_S5_QUANT_"+reason)

def source_url(url,host):
    p=urlsplit(url)
    require(p.scheme=="https" and p.hostname==host and p.username is None
            and p.password is None and p.query=="" and p.fragment=="" and p.port is None,
            "URL_OR_HOST_IDENTITY")
    try: v=ipaddress.ip_address(host)
    except ValueError: v=None
    require(v is None or v.is_global,"PRIVATE_ADDRESS")
    return url

def validate_manifest(m):
    require(m.get("format")==MANIFEST_FORMAT
            and m.get("target_id")==TARGET
            and m.get("mode")=="PUBLIC_READ_ONLY_BACKFILL"
            and m.get("cutoff")==AS_OF
            and m.get("external_query_policy")=="NO_PRIVATE_CACHE_DERIVED_QUERY_NO_GENERAL_SEARCH_INPUT"
            and m.get("live_registration") is False
            and m.get("paid_model_api") is False
            and m.get("research_scope")==
                "ANTARES_STANDARD_FIRM_CONTRACT_VS_AUTHORIZED_TRISO_THROUGHPUT_NO_AUTO_FORECAST",
            "MANIFEST_CONTRACT_CHANGED")
    prior=m.get("fixed_prior_public_proof",{})
    require(prior=={"run_id":PRIOR_S5_RUN,"artifact_id":PRIOR_S5_ARTIFACT,
                    "artifact_digest":PRIOR_S5_DIGEST,"prior_head_sha":PRIOR_S5_SHA},
            "PRIOR_S5_PROOF_CHANGED")
    src=m.get("sources",[])
    require(isinstance(src,list) and len(src)==2 and
            {x.get("id") for x in src}==SOURCE_IDS,
            "TWO_OFFICIAL_SOURCES_REQUIRED")
    for x in src:
        require(all(isinstance(x.get(k),str) and x[k] for k in
                    ("url","issuer","host","period_end","source_type")),
                "SOURCE_METADATA_MISSING")
        source_url(x["url"],x["host"])
        require(x["period_end"]=="2026-09-30"
                and x["source_type"] in
                    ("ISSUER_OFFICIAL_SEC_10Q","ISSUER_OFFICIAL_2026Q3_RELEASE"),
                "WRONG_SOURCE_REPORTING_PERIOD")
        pub=x.get("filing_date") or x.get("published_date")
        require(pub is not None and pub<=AS_OF,"FUTURE_OFFICIAL_ORIGINAL")
    return src

def verify_prior(prior):
    require(prior.get("format")=="bct-s5-public-primary-original-crosscheck-v1"
            and prior.get("case_count")==8
            and prior.get("attempted_public_primary_urls")==8
            and prior.get("fetched_bodies")==8
            and prior.get("candidate_or_LIVE_writes")==0
            and prior.get("strict_eligible_supply_demand_pairs")==0
            and prior.get("no_source_text_exported") is True
            and prior.get("S4_11_originals_or_private_epoch_modified") is False,
            "PREVIOUS_PUBLIC_PROOF_NOT_VERIFIED")
    return True

class HTMLVisible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0
        self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript") and self.skip:self.skip-=1
    def handle_data(self,value):
        if not self.skip and value.strip():self.items.append(value)
    def visible(self):
        return " ".join(" ".join(self.items).split())

def visible_text(raw):
    p=HTMLVisible()
    p.feed(raw.decode("utf-8",errors="replace"))
    return p.visible()

def bound_fact(text,anchor,pattern,window):
    # The documented source fragment must be in its correct contract or
    # capacity subsection. A number elsewhere on the issuer page is not proof.
    starts=[m.start() for m in re.finditer(re.escape(anchor),text,re.I)]
    for start in starts:
        scope=text[start:start+window]
        found=re.search(pattern,scope,re.I|re.S)
        if found is not None:
            a=start+found.start();b=start+found.end()
            return {"start":a,"end":b,"source_span_sha256":sha(text[a:b])}
    return None

def extract_case(source,raw,final=None,error=None):
    case={"source_id":source["id"],"origin_url":source["url"],
          "issuer":source["issuer"],"role":"RESEARCH_ONLY_EVIDENCE_EXTRACT",
          "published_or_filed_declared":source.get("filing_date",source.get("published_date")),
          "report_period_end":source["period_end"],
          "status":"ACCESS_HOLD" if raw is None else "FETCHED_PUBLIC_ORIGINAL_RESEARCH_ONLY",
          "strict_original_global_verification":"NOT_CLAIMED",
          "fact_receipts":[],
          "source_inference_api_calls":0,"automatic_live_candidates":0}
    if raw is not None:
        source_url(final,source["host"])
        require(final==source["url"],"CROSS_OR_CHANGED_FINAL_URL")
        txt=visible_text(raw)
        require(len(txt)>=1500,"NO_ACCESSIBLE_OFFICIAL_DOCUMENT_BODY")
        require(source["issuer"].casefold().split()[0] in txt.casefold(),
                "OFFICIAL_ISSUER_NOT_OBSERVED")
        case.update(raw_sha256=sha(raw),visible_sha256=sha(txt),
                    public_visible_characters=len(txt))
    else:
        txt=None
        case["error_type"]=error or "ORIGINAL_ACCESS_NOT_VERIFIED"
    for id,value,unit,semantics,anchor,pattern,window in FACTS[source["id"]]:
        loc=bound_fact(txt,anchor,pattern,window) if txt is not None else None
        case["fact_receipts"].append({
           "fact_id":id,"state":"SOURCE_LOCATOR_HASH_VERIFIED" if loc else "HOLD_NO_MATCHED_ORIGINAL_SPAN",
           "value":value if loc else UNKNOWN,
           "unit":unit,
           "meaning":semantics,
           "locator":loc
        })
    require(len(case["fact_receipts"])==len(FACTS[source["id"]]),"FACT_COUNT_CHANGED")
    return case

def derive(manifest,prior,cases):
    validate_manifest(manifest);verify_prior(prior)
    require({x["source_id"] for x in cases}==SOURCE_IDS and len(cases)==2,
            "TWO_OFFICIAL_CASES_REQUIRED")
    found={}
    for c in cases:
        if c["status"]=="FETCHED_PUBLIC_ORIGINAL_RESEARCH_ONLY":
            require(all(re.fullmatch("[0-9a-f]{64}",c[k]) for k in
                        ("raw_sha256","visible_sha256")),"SOURCE_HASH_INTEGRITY")
        require(c.get("automatic_live_candidates")==0 and
                c.get("source_inference_api_calls")==0,
                "UNAUTHORIZED_SIDE_EFFECT")
        for fact in c["fact_receipts"]:
            require(fact["fact_id"] not in found and fact["fact_id"] in PINNED_FACT_IDS,
                    "FACT_DUPLICATE_OR_UNKNOWN")
            state=fact["state"]
            require(state in ("SOURCE_LOCATOR_HASH_VERIFIED","HOLD_NO_MATCHED_ORIGINAL_SPAN"),
                    "SOURCE_FACT_STATE")
            if state=="SOURCE_LOCATOR_HASH_VERIFIED":
                loc=fact["locator"]
                require(type(loc)==dict and type(loc.get("start")) is int
                        and type(loc.get("end")) is int and
                        loc["start"]<loc["end"] and loc["start"]>=0 and
                        re.fullmatch("[0-9a-f]{64}",loc.get("source_span_sha256","")),
                        "FACT_LOCATOR_INVALID")
            else:
                require(fact["value"]==UNKNOWN and fact["locator"] is None,
                        "HELD_FACT_VALUE_MUST_BE_UNKNOWN")
            found[fact["fact_id"]]=fact
    require(set(found)==PINNED_FACT_IDS,"INCOMPLETE_FIXED_FACT_INVENTORY")
    def val(id):
        return found[id]["value"]
    # Neither firm quantity due by end 2030 nor installed throughput at
    # Sep 2026 can be distributed into an individual 2027-2030 delivery year.
    # A capacity ceiling does not establish eligible unreserved customer supply.
    annual={
      yr:{"Antares_firm_TRISO_deliveries_MTU":UNKNOWN,
          "qualified_customer_eligible_unreserved_TRISO_output_MTU":UNKNOWN,
          "same_scope_physical_gap_MTU":UNKNOWN,
          "conclusion":"NOT_COMPARABLE_UNKNOWN_BOTH_ANNUAL_DENOMINATORS"}
      for yr in PERIODS
    }
    missing=[
       "CUSTOMER_FIRM_YEAR_BY_YEAR_DELIVERY_REQUIREMENT",
       "SUPPLY_ACTUALLY_AVAILABLE_AND_UNRESERVED_FOR_THIS_CUSTOMER",
       "IDENTICAL_FUEL_ASSAY_FORM_AND_CUSTOMER_QUALIFICATION",
       "BOTH_SIDES_SAME_CUSTOMER_REGION_AND_DELIVERY_PERIOD",
       "EVIDENCE_TWO_INDEPENDENT_ECONOMIC_ORIGINAL_EVENTS",
       "EXISTING_COMMITMENTS_AND_MATERIAL_INVENTORY_RECONCILIATION",
       "ALTERNATE_BWXT_FABRICATOR_CAPACITY_AND_QUALIFICATION",
    ]
    # Do not multiply an already yield-based throughput by process yield again.
    return {
      "format":FORMAT,"date":AS_OF,"target_id":TARGET,
      "research_status":"PASS_TYPED_FINANCIAL_SOURCE_CONSTRAINTS_NOT_A_SHORTAGE_CLAIM",
      "session5_total_status":"PARTIAL_REQUIRED_PHYSICAL_SAME_PERIOD_EVIDENCE_NOT_OBTAINED",
      "official_originals_attempted":2,
      "official_originals_fetched":sum(c["status"]=="FETCHED_PUBLIC_ORIGINAL_RESEARCH_ONLY" for c in cases),
      "verified_numeric_or_temporal_fact_count":sum(x["state"]=="SOURCE_LOCATOR_HASH_VERIFIED" for x in found.values()),
      "verified_fact_ids":sorted(k for k,x in found.items() if x["state"]=="SOURCE_LOCATOR_HASH_VERIFIED"),
      "source_holds":sorted(k for k,x in found.items() if x["state"]!="SOURCE_LOCATOR_HASH_VERIFIED"),
      "firm_contract_cumulative_MTU_by_2030":val("STDN_FIRM_FABRICATION_TOTAL_MTU"),
      "Antares_customer_optional_MTU_not_firm":val("STDN_OPTION_NOT_COMMITTED_MTU"),
      "Antares_firm_latest_delivery_date":val("STDN_FIRM_DELIVERY_LATEST"),
      "Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30":
          val("STDN_INSTALLED_AUTHORIZED_THROUGHPUT_MTU_Y"),
      "Standard_building_envelope_MTU_per_year_not_operational":
          val("STDN_BUILDING_THEORETICAL_MTU_Y"),
      "Standard_overall_process_yield_pct_not_second_multiplier":
          val("STDN_OVERALL_PROCESS_YIELD_PERCENT"),
      "standard_operational_future_output_customer_free_MTU":UNKNOWN,
      "Centrus_16_centrifuge_cascade_not_MTU_per_year":
          val("CENTRUS_OPERATING_CASCADE_COUNT"),
      "annual_comparison":annual,
      "missing_required_evidence":missing,
      "strict_independent_eligible_demand_supply_pairs":"NOT_EVALUATED_REQUIRE_SOURCE_COMPLETE_PHYSICAL_FACTS",
      "confirmed_shortage":"NOT_ESTABLISHED",
      "new_early_candidates":0,
      "LIVE_writes":0,"protected_early_strict_engine_executions":0,
      "source_text_exported":False,"private_original_source_access":False,
      "prior_8_public_source_pilot_reused":True,
      "prior_public_run_id":PRIOR_S5_RUN,
      "forecast_accuracy":"UNVERIFIED"
    }

def save_and_verify(dest,summary,cases):
    dest=Path(dest)
    require(not dest.exists(),"NO_OVERWRITE_ALLOWED")
    dest.mkdir(parents=True)
    db=dest/"research.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE cases(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL)")
        for c in cases:
            s=canon(c)
            conn.execute("INSERT INTO cases VALUES (?,?,?)",(c["source_id"],sha(s),s))
    summary=dict(summary)
    summary["sqlite_sha256"]=sha(db.read_bytes())
    summary["case_integrity_sha256"]=sha(canon(sorted(cases,key=lambda c:c["source_id"])))
    (dest/"summary.json").write_text(canon(summary)+"\n")
    fresh_readback(dest)
    return summary

def fresh_readback(dest):
    p=Path(dest)
    summary=json.loads((p/"summary.json").read_text())
    file=p/"research.sqlite3"
    require(sha(file.read_bytes())==summary.get("sqlite_sha256"),"REQUERY_SQLITE_SHA")
    with sqlite3.connect(file.resolve().as_uri()+"?mode=ro",uri=True) as c:
        require(c.execute("PRAGMA integrity_check").fetchone()==("ok",),"REQUERY_SQLITE_INTEGRITY")
        rows=c.execute("SELECT id,sha256,payload FROM cases ORDER BY id").fetchall()
    require(len(rows)==2,"REQUERY_SOURCE_COUNT")
    cases=[]
    for ident,h,payload in rows:
        require(sha(payload)==h,"REQUERY_PAYLOAD_HASH")
        x=json.loads(payload)
        require(x["source_id"]==ident and not any(k in x for k in
                 ("body","raw","source_quote","article_text","html")),
                 "REQUERY_SOURCE_ID_OR_CONTENT_LEAK")
        cases.append(x)
    require(sha(canon(cases))==summary["case_integrity_sha256"]
            and summary["LIVE_writes"]==0
            and summary["new_early_candidates"]==0
            and summary["confirmed_shortage"]=="NOT_ESTABLISHED"
            and all(x["same_scope_physical_gap_MTU"]==UNKNOWN
                    for x in summary["annual_comparison"].values()),
            "REQUERY_INVALID_ANALYTIC_CLAIM")
    return {"status":"PASS_QUANTITATIVE_SOURCE_FREE_SQLITE_READBACK",
            "originals":len(cases),"fact_count":summary["verified_numeric_or_temporal_fact_count"]}

def run(args):
    from bct import target_acquisition as acquisition
    manifest=json.loads(args.manifest.read_text())
    sources=validate_manifest(manifest)
    prior=json.loads(args.prior.read_text())
    verify_prior(prior)
    cases=[]
    for src in sources:
        try:
            raw,final,status,ctype=acquisition.fetch(src["url"])
            require(status==200 and "html" in ctype.lower(),"ORIGINAL_NOT_HTML_200")
            case=extract_case(src,raw,final=final)
        except Exception as exc:
            case=extract_case(src,None,error=type(exc).__name__)
        cases.append(case)
        print("S5_QUANT_ORIGINAL="+canon({
          "id":case["source_id"],"status":case["status"],
          "verified_facts":sum(f["state"]=="SOURCE_LOCATOR_HASH_VERIFIED" for f in case["fact_receipts"]),
          "facts_held":sum(f["state"]!="SOURCE_LOCATOR_HASH_VERIFIED" for f in case["fact_receipts"]),
          "failure_kind":case.get("error_type","NONE")}),flush=True)
    report=derive(manifest,prior,cases)
    save_and_verify(args.out,report,cases)
    print("S5_QUANT_BOUND_ANALYSIS="+canon({
       "status":report["research_status"],"source_fetches":report["official_originals_fetched"],
       "source_bound_facts":report["verified_numeric_or_temporal_fact_count"],
       "firm_cumulative_MTU":report["firm_contract_cumulative_MTU_by_2030"],
       "operational_MTU_per_year":report["Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30"],
       "building_only_MTU_per_year":report["Standard_building_envelope_MTU_per_year_not_operational"],
       "annual_supply_gap_MTU":UNKNOWN,
       "confirmed_shortage":report["confirmed_shortage"],
       "LIVE_writes":report["LIVE_writes"]}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path)
    p.add_argument("--prior",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.verify_only:
        print("S5_QUANT_FRESH_REQUERY="+canon(fresh_readback(a.out)));return
    require(a.manifest is not None and a.prior is not None,"INPUTS_REQUIRED")
    run(a)

if __name__=="__main__":
    main()
