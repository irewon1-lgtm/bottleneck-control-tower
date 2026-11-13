"""BCT V4 research-only, source-addressed semantic signal leads.

This *never* verifies qualified supply, compares demand/supply quantities,
promotes S-stages, changes the production filter, or supplies a gold label.
Use the existing version-locked source scope reader rather than copying its
physical-product grammar or filling missing fields from issuer/sector names.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import re
from typing import Any

from . import precursor_scope_reader as source_scope
from .future_bottleneck import screen as old_screen

VERSION="bct-v4-shadow-sentence-local-1"
SIGNALS=("DEMAND","SUPPLY","RELIEF")
STATEMENTS={
    "DEMAND":re.compile(
        r"\b(?:orders?|backlogs?|offtake|reservations?|purchase agreements?|"
        r"purchases?|demand|procurement|bookings?|contract awards?|deliveries?)\b",re.I),
    "SUPPLY":re.compile(
        r"\b(?:suppl(?:y|ies|ier|iers)|production|manufactur\w*|"
        r"capacit(?:y|ies)|fabrication|qualification|certification|"
        r"lead[\s-]*times?|output|inventor(?:y|ies)|plant|factory|"
        r"mills?|mines?|shipment|shipping)\b",re.I),
    "RELIEF":re.compile(
        r"\b(?:capacit(?:y|ies)|production|manufactur\w*|"
        r"suppl(?:y|ies|ier|iers)|lead[\s-]*times?|qualification|"
        r"certification|plant|factory|factory lines?|output|"
        r"inventory|backlog|deliveries|substitut\w*|alternatives?)\b",re.I),
}
CHANGES={
    "DEMAND":re.compile(
        r"\b(?:increas\w*|ris(?:e|es|en|ing)|rose|surge\w*|"
        r"grow\w*|grew|doubled?|tripled?|accelerat\w*|"
        r"placed|signed|awarded|secured|booked|committed|"
        r"firm|binding|record[- ]high|outpac\w*)\b",re.I),
    "SUPPLY":re.compile(
        r"\b(?:shortage\w*|insufficient|shortfall\w*|"
        r"constrain\w*|delayed?|postponed?|suspend\w*|"
        r"halt\w*|stop\w*|paused?|shutdown\w*|"
        r"shut down|closed?|closure\w*|outages?|disrupt\w*|"
        r"cut(?:s|ting)?|reduc\w*|bottleneck\w*|"
        r"scarcity|limited|exceed\w*|longer|extended|"
        r"tight(?:en\w*)?|backlog\w*)\b",re.I),
    "RELIEF":re.compile(
        r"\b(?:expan\w*|increas\w*|add(?:s|ed|ing)?|"
        r"ramp(?:ed|ing|s)?|recover\w*|restor\w*|"
        r"normaliz\w*|reopen\w*|restart\w*|"
        r"qualif(?:y|ied|ication)|certif(?:y|ied|ication)|"
        r"second source|alternative\w*|substitut\w*|"
        r"reduce\w*|shorten\w*|commission\w*)\b",re.I),
}
QUALIFIER=re.compile(
    r"\b(?:may|might|could|would|if|unless|plans?|planned|planning|"
    r"expects?|expected|project(?:s|ed|ion)?|forecast\w*|"
    r"potential|proposal|proposed|aims?|seeks?|target(?:s|ed)?|"
    r"not|never|no|denied|rumou?r\w*|contingent)\b",re.I)
MONEY=re.compile(r"(?:[$€£]\s*\d|(?:USD|EUR|GBP)\s*\d)",re.I)
PHYSICAL_QTY=re.compile(
    r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(tonnes?|tons?|metric tons?|units?|pieces?|wafers?|"
    r"motors?|transformers?|turbines?|batteries|slots?)\b",re.I)
DELIVERY_NEED=re.compile(
    r"\b(?:needed|need|required|delivery required|delivery needed)\s+by\s+"
    r"(20\d{2}-\d{2}-\d{2})\b",re.I)
CAPACITY_READY=re.compile(
    r"\b(?:available|production ready|qualified|certified|"
    r"shipments start)\s+(?:on|from|by)\s+(20\d{2}-\d{2}-\d{2})\b",re.I)
DATES=re.compile(
    r"\b(?:20\d{2}-\d{2}-\d{2}|Q[1-4]\s+20\d{2}|(?:first|second)\s+half\s+of\s+20\d{2}|20\d{2})\b",re.I)
BANNED_SIMPLE=re.compile(
    r"\b(?:newsletter|advertisement|share this article|"
    r"privacy policy|cookie settings|all rights reserved|"
    r"read more|related articles)\b",re.I)
NEGATION=re.compile(r"\b(?:no|not|never|denied|without)\b",re.I)


def _span(body,begin,end):
    if not 0<=begin<end<=len(body):
        raise ValueError("SEMANTIC_SOURCE_LOCATOR_INVALID")
    return {"start":begin,"end":end}


def _sentences(body):
    """Keep absolute offsets and skip isolated publisher UI."""
    dummy={"document_id":"SHADOW","body_sha256":hashlib.sha256(body.encode()).hexdigest(),
           "body":body,"origin_url":None,"origin_publisher":None}
    lines,_=source_scope.allowed_lines(dummy)
    for line in source_scope.sentences(dummy,lines):
        if not BANNED_SIMPLE.search(line["quote"][:120]):
            yield line


def _roles(sentence):
    # Same-sentence necessary co-occurrence is only a lead, not causal proof.
    result=[]
    for name in SIGNALS:
        if STATEMENTS[name].search(sentence) and CHANGES[name].search(sentence):
            result.append(name)
    return result


def _local_number(quote, role, product_bound, uncertain):
    """Do not treat sale proceeds, investment money, or unrelated quantities as capacity."""
    if uncertain or not product_bound or MONEY.search(quote):
        return None,None
    matches=list(PHYSICAL_QTY.finditer(quote))
    if len(matches)!=1:
        return None,None
    if role=="DEMAND" and not re.search(
        r"\b(?:orders?|backlog|demand|purchase|reservation|offtake)\b",quote,re.I):
        return None,None
    if role=="SUPPLY" and not re.search(
        r"\b(?:production|capacity|qualified supply|output)\b",quote,re.I):
        return None,None
    if role=="RELIEF":
        return None,None
    return float(matches[0][1].replace(",","")),matches[0][2].lower()


def _local_refs(doc, role, row, scope):
    body=doc["body"]
    quote=row["quote"]
    start,end=row["start"],row["end"]
    assert quote==body[start:end]
    product=scope.get("product")
    validated_product=bool(product and product.get("value"))
    raw_periods=[{"value":m[0],
                  "locator":_span(body,start+m.start(),start+m.end()),
                  "source_status":"RAW_REFERENCE_ONLY"}
                 for m in DATES.finditer(quote)]
    is_uncertain=bool(QUALIFIER.search(quote))
    # It is important to preserve a lead even when its product binding is UNKNOWN.
    bound=bool(validated_product)
    qty,unit=_local_number(quote,role,bound,is_uncertain)
    needed=DELIVERY_NEED.search(quote) if not is_uncertain and role=="DEMAND" else None
    ready=CAPACITY_READY.search(quote) if not is_uncertain and role in ("SUPPLY","RELIEF") else None
    if role=="RELIEF":
        qty=unit=None
    item={
       "role":role,"document_id":doc["document_id"],
       "body_sha256":doc["body_sha256"],
       "source_identity":doc.get("origin_url"),
       "locator":_span(body,start,end),
       "source_quote":quote[:260],  # preview is private in live-source pilot; do not publish raw text
       "product":product["value"] if bound else "UNKNOWN",
       "product_locator":product.get("locator") if bound else None,
       "product_binding":"SOURCE_BOUND" if bound else "UNRESOLVED",
       "specification":scope.get("specification",{}).get("value","UNKNOWN"),
       "region":scope.get("region",{}).get("value","UNKNOWN"),
       "customer_group":scope.get("customer_group",{}).get("value","UNKNOWN"),
       "supply_pool":scope.get("supply_pool",{}).get("value","UNKNOWN"),
       "supplier_qualification_verified":False,
       "qualified_pool_capacity_covered":False,
       "quantity":qty,"unit":unit or "UNKNOWN",
       "need_date":needed[1] if needed else None,
       "available_date":ready[1] if ready else None,
       "period_references":raw_periods,
       "source_language_status":"CONDITIONAL_OR_NEGATED"
           if is_uncertain else "ASSERTED_OR_REPORTED_NEEDS_SOURCE_REVIEW",
       "source_fact_verified":False,
       "independent_evidence_verified":False,
       "false_positive_review_required":bool(NEGATION.search(quote)),
       "needs_exact_customer_period":True,
       "target_stage":"NOT_ASSESSED",
       "engine_version":VERSION
    }
    if bound:
        loc=product["locator"]
        if body[loc["start"]:loc["end"]] != product["value"]:
            raise ValueError("SEMANTIC_PRODUCT_LOCATOR_MISMATCH")
    return item


def analyze(body:str, *, document_id:str, origin_url:str, prior_screening=None,
            body_status:str="UNKNOWN", provenance_verified:bool=False):
    """Return source-located leads only. Raw body is never returned."""
    if not isinstance(body,str) or not body or len(body)>10_000_000:
        raise ValueError("SEMANTIC_INVALID_BODY")
    if not document_id or not isinstance(origin_url,str) or not origin_url.startswith("https://"):
        raise ValueError("SEMANTIC_INVALID_SOURCE_IDENTITY")
    bodyhash=hashlib.sha256(body.encode()).hexdigest()
    doc={"document_id":document_id,"body":body,"body_sha256":bodyhash,
         "origin_id":None,"origin_url":origin_url,"origin_publisher":None}
    raw_events=[]
    for r in _sentences(body):
        for role in _roles(r["quote"]):
            raw_events.append({
                "role":role,"locator":{"start":r["start"],"end":r["end"]},
                "source_quote":r["quote"],"kind":"RESEARCH_LEAD"})
    resolved,_=source_scope.read_scopes(doc,raw_events,lambda _: {})
    if len(resolved)!=len(raw_events) or not source_scope.validate_references(doc,resolved):
        raise ValueError("SEMANTIC_SOURCE_REFERENCE_INCONSISTENT")
    leads=[]
    for event in resolved:
        row={"start":event["locator"]["start"],"end":event["locator"]["end"],
             "quote":event["source_quote"]}
        scope=event.get("scope") or {}
        leads.append(_local_refs(doc,event["role"],row,scope))
    # Recheck the literal locator of every extraction, never fill source text missing.
    for e in leads:
        source_text=body[e["locator"]["start"]:e["locator"]["end"]]
        if not source_text.startswith(e["source_quote"]):
            raise ValueError("SEMANTIC_EVIDENCE_LOCATION_INCONSISTENT")
    before=prior_screening if isinstance(prior_screening,dict) else old_screen(body)
    modes=Counter(e["role"] for e in leads)
    products=sorted({e["product"].casefold() for e in leads if e["product"]!="UNKNOWN"})
    return {
        "version":VERSION,
        "document_id":document_id,
        "origin_url":origin_url,
        "body_sha256":bodyhash,
        "body_status":body_status,
        "provenance_verified":provenance_verified is True,
        "research_usable_full_original":body_status=="FULL" and provenance_verified is True,
        "literal_lead_counts":{k:modes[k] for k in SIGNALS},
        "literal_leads":leads,
        "identified_physical_products":len(products),
        "unknown_product_leads":sum(e["product"]=="UNKNOWN" for e in leads),
        "qualified_supply_comparison_ready":False,
        "S1_S2_S3_assigned":False,
        "prior_body_screening_paths":before.get("discovery_paths",[]),
        "prior_body_screening_candidate":before.get("candidate") is True,
        "confidence":"UNVERIFIED_SEMANTIC_SHADOW_ONLY"
    }


def public_receipt(value):
    """Never redistribute third-party full text or excerpt with research metrics."""
    if value.get("version")!=VERSION:
        raise ValueError("SEMANTIC_VERSION_MISMATCH")
    return {k:v for k,v in value.items() if k!="literal_leads"}|{
        "literal_leads_count":len(value.get("literal_leads",[])),
        "source_quote_redistributed":False,
        "source_locators_only":True
    }
