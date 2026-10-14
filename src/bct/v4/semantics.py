"""Conservative, source-bound meaning guards; never a general accuracy verdict.

Inputs already passed exact quotation validation. No offsets, facts, quantities,
customer identities, qualifications or S stages are invented here. Unsupported
claims remain in the audit, while the usable field becomes UNKNOWN/null.
"""
from copy import deepcopy
import calendar
import re

from bct.precursor_scope_reader import FIELDS, GENERIC, NONPRODUCT_IDENTIFIER, REGION, SPEC

VERSION = "bct-v4-semantics-2"
PHYSICAL = ("PHYSICAL_PRODUCT", "PRODUCT_FAMILY", "MANUFACTURING_EQUIPMENT", "PRODUCTION_SLOT")
TIME_WORDS = re.compile(r"\b(?:year|month|week|quarter|" + "|".join(calendar.month_name[1:]) + r")\b", re.I)
FAMILY = r"(?:SMRs|reactors|battery cells|batteries|transceivers|heat pumps|turbines|transformers|wafers|chips|trucks|engines|lasers|connectors)"
MONEY = re.compile(r"[$€£¥]|\b(?:USD|EUR|GBP|JPY|KRW|dollars?|euros?|won|investment|revenue|funding|grants?|subsid(?:y|ies))\b", re.I)
FUNDING = re.compile(r"\b(?:funding|grants?|subsid(?:y|ies)|financing|investment|financial aid)\b|\b(?:awarded|granted)\s+[$€£¥]", re.I)
PLAN = re.compile(r"\b(?:plans?|planned|intends?|proposed|scheduled|will|would|aims?|targets?)\b", re.I)
FORECAST = re.compile(r"\b(?:expects?|forecast\w*|projected|anticipated|may|might|could)\b", re.I)
NEGATION = re.compile(r"\b(?:not(?!\s+only\b)|never|no|failed to)\b|\b(?:hasn|haven|didn|doesn|isn|aren)[’']t\b", re.I)
PAST = re.compile(r"\b(?:signed|placed|received|secured|awarded|granted|selected|established|announced|approved|delivered|shipped|produced|completed|commissioned|fell|rose|shortened|expanded|decreased|increased|stopped|delayed|reduced|grew)\b", re.I)
EVENTS = {
    "DEMAND_INCREASE": r"\b(?:signed|placed|received|secured|awarded)\b.{0,70}\b(?:orders?|(?:purchase )?contracts?)\b|\borders?\b.{0,55}\b(?:increase\w*|grew|rose)\b",
    "SUPPLY_INCREASE": r"\b(?:production|capacity|output|supply)\b.{0,70}\b(?:increase\w*|expand\w*|doubled|rose)\b|\b(?:increase\w*|expand\w*)\b.{0,50}\b(?:production|capacity)\b|\b(?:started|began|commenced|resumed)\b.{0,50}\bproduction\b|\b(?:commissioned|became operational|began operating)\b",
    "SUPPLY_DECREASE": r"\b(?:production|capacity|output|supply)\b.{0,60}\b(?:decrease\w*|declined|reduced|stopped|fell|cut)\b|\b(?:shut down|ceased production)\b",
    "SUPPLY_DELAY": r"\b(?:production|delivery|deliveries|qualification)\b.{0,60}\b(?:delayed|postponed)\b|\b(?:delayed|postponed)\b.{0,50}\b(?:production|delivery|deliveries)\b|\blead times?\b.{0,50}\b(?:lengthened|increased)\b",
    "RELIEF": r"\bsurplus\b|\bavailable capacity\b|\binventory\b.{0,65}\bincreased\b|\blead times?\b.{0,65}\b(?:shortened|fell|decreased)\b|\bshortage\b.{0,40}\b(?:eased|ended)\b|\bno longer delayed\b",
}
UNITS = r"(?:units?|systems?|aircraft|helicopters?|drones?|barrels?|pieces?|cells?|batteries|chips?|wafers?|turbines?|pumps?|reactors?|transceivers?|transformers?|engines?|vehicles?|trucks?|tonnes?|tons?|kg|kWh|MWh|GWh|MW|GW|litres?|liters?|slots?)"
MODIFIER = r"(?:(?:new|advanced|commercial|large[- ]scale|industrial|optical|battery|lithium[- ]ion|high[- ]purity|nuclear|silicon|solar|gas|wind|heat)\s+)"
AMOUNT = r"(?:\d[\d,.]*(?:\s+(?:million|billion|thousand))?|one|two|three|four|five|six|seven|eight|nine|ten)"
QUANTITY = re.compile(r"\b(?P<amount>" + AMOUNT + r")\s+(?:" + MODIFIER + r")*(?P<unit>" + UNITS + r")\b", re.I)
PHYSICAL_COUNT = re.compile(r"\b(?:produced|delivered|shipped|ordered|purchased|bought|order|orders|production|capacity|output|supply|inventory|deployment|needs|required)\b", re.I)


def modality(text):
    if NEGATION.search(text):
        return "NEGATED"
    if FORECAST.search(text):
        return "FORECAST"
    if PLAN.search(text):
        return "PLAN"
    return "ACTUAL"


def clauses(item):
    # These local spans only scope meaning; citation offsets are never changed.
    text = item["context"]["quote"]
    ranges, start = [], 0
    for split in re.finditer(r";\s*|\.\s+(?=[A-Z])|\s+(?:but|whereas|while)\s+", text):
        ranges.append((start, split.start(), text[start:split.start()]))
        start = split.end()
    ranges.append((start, len(text), text[start:]))
    return ranges


def product_clauses(item):
    name = item["entity"]["value"] or ""
    return [part for part in clauses(item) if name and name in part[2]]


def fact_scope(item, fact):
    # A long quotation cannot attach a fact about another product in a different
    # clause. Use the exact fact value, not a model-supplied position hint.
    parts = product_clauses(item)
    matches = [text for _, _, text in parts if fact["value"] in text]
    if len(matches) != 1:
        return None
    if not item["context"]["start"] <= fact["start"] < fact["end"] <= item["context"]["end"]:
        return None
    return matches[0]


def identity(item):
    name = item["entity"]["value"] or ""
    if NONPRODUCT_IDENTIFIER.search(name):
        return "DISCLOSURE_HEADING", "DISCLOSURE_IDENTIFIER"
    if name.casefold().strip(" .,:;") in GENERIC:
        return "GENERAL_EXPRESSION", "GENERIC_IDENTIFIER"
    if re.search(r"\b(?:projects?|programs?|initiatives?)$", name, re.I):
        return "PROJECT", "EXPLICIT_PROJECT_HEAD"
    if re.search(r"\b(?:production|foundry|manufacturing) slots?$", name, re.I):
        return "PRODUCTION_SLOT", "EXPLICIT_SLOT_HEAD"
    if re.search(r"\b(?:equipment|machines?|manufacturing tools?)$", name, re.I):
        return "MANUFACTURING_EQUIPMENT", "EXPLICIT_EQUIPMENT_HEAD"
    if re.search(r"\b" + FAMILY + r"$", name, re.I):
        return "PRODUCT_FAMILY", "EXPLICIT_PHYSICAL_FAMILY_HEAD"
    return item["kind"], "UNKNOWN_MODEL_CLASSIFICATION"


def region_constructions(entity, text):
    # Geographic vocabulary is reused from the existing reader. Require a
    # literal relation to this product, rather than any location in a document.
    if not entity:
        return []
    return list(re.finditer(r"\b(?P<region>" + REGION + r")\s+"
        r"(?:deployment|production|manufacturing|delivery)\s+of\s+"
        + re.escape(entity) + r"(?!\w)", text, re.I))


def literal_region_fields(item):
    """One unambiguous, missing region candidate; the caller must bind/verify it.

    Only the already quoted context is read. No fuzzy match, outside-window
    lookup, party inference, production claim, or extra API request is made.
    """
    facts = item["facts"]
    if identity(item)[0] not in PHYSICAL or any(f["field"] == "region" and f["value"] is not None for f in facts):
        return item
    matches = region_constructions(item["entity"]["value"], item["context"]["quote"])
    if len(matches) != 1 or (not any(f["field"] == "region" for f in facts) and len(facts) >= 16):
        return item
    candidate = {"field": "region", "value": matches[0]["region"], "quote": item["context"]["quote"]}
    result = deepcopy(item)
    result["facts"] = [candidate if f["field"] == "region" else f for f in result["facts"]]
    if not any(f["field"] == "region" for f in facts):
        result["facts"].append(candidate)
    return result


def event_reading(item):
    name = item["entity"]["value"] or ""
    wanted = item["role"]
    parts = product_clauses(item) if item["kind"] in PHYSICAL else []
    # A planned pronoun clause in the same one-product context stays a plan,
    # never actual qualified capacity. Named second-product clauses are excluded.
    if parts and wanted in ("SUPPLY_INCREASE", "SUPPLY_DECREASE", "SUPPLY_DELAY", "RELIEF"):
        for part in clauses(item):
            text = part[2].strip()
            if (part not in parts and re.match(r"(?:it|its|they|their)\b", text, re.I)
                    and (PLAN.search(text) or FORECAST.search(text))
                    and not re.search(r"\b" + FAMILY + r"\b", text, re.I)):
                parts.append(part)
    candidates = []
    for _, _, text in parts:
        if re.search(r"\bexecutive orders?\b", text, re.I):
            continue
        for role, pattern in EVENTS.items():
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            mode_text = text[:match.end()]
            if role == "RELIEF" and re.search(r"\bno longer delayed\b", match[0], re.I):
                mode_text = re.sub(r"\bno longer\b", "", mode_text, flags=re.I)
            mode = modality(mode_text)
            # Expansion financed/to-be-developed is not operational expansion.
            if FUNDING.search(text) and role in ("DEMAND_INCREASE", "SUPPLY_INCREASE"):
                completed = re.search(r"\b(?:completed|commissioned|began|started|resumed)\b.{0,60}\b(?:production|capacity|line|plant)\b|\b(?:production|capacity|output)\b.{0,40}\b(?:expanded|increased|doubled)\b", text, re.I)
                purchase = re.search(r"\b(?:purchase|procurement|supply) contract\b", text, re.I)
                if not completed and not purchase:
                    continue
            if role == "DEMAND_INCREASE" and re.search(r"\b(?:research|development|consulting|marketing) (?:contract|agreement)\b|\bcontracts? (?:to|for) (?:research|develop\w*|consult\w*|marketing|licens\w*|feasibility)\b", text, re.I):
                continue
            candidates.append((role, mode, text))
    chosen = next((x for x in candidates if x[0] == wanted), None)
    # A literal signed purchase of this object is not replaced by a later
    # planned output/operation clause merely because the model wanted supply.
    direct_order = r"\b(?:orders?|purchase contracts?)\s+(?:for|of)\s+(?:(?:" + AMOUNT + r"|a|an|the|new|additional)\s+)*" + re.escape(name) + r"(?![\w-])"
    actual_order = next((x for x in candidates if x[0] == "DEMAND_INCREASE" and x[1] == "ACTUAL"
                         and name and re.search(direct_order, x[2], re.I)), None)
    if item.get("source_reference_protocol") and actual_order and (chosen is None or chosen[1] in ("PLAN", "FORECAST")):
        chosen = actual_order
    if chosen and chosen[1] == "NEGATED":
        reversal = next((x for x in candidates if x[0] == "RELIEF" and x[1] != "NEGATED"
                         and re.search(r"\bno longer delayed\b", x[2], re.I)), None)
        chosen = reversal or chosen
    if chosen is None and len({x[0] for x in candidates}) == 1:
        chosen = candidates[0]
    if chosen:
        role, mode, text = chosen
        return ("UNKNOWN" if mode == "NEGATED" else role), mode, text
    text = " ".join(x[2] for x in parts) or item["context"]["quote"]
    mode = modality(text)
    if mode == "ACTUAL" and re.search(r"\b(?:revenue|earnings|cash flow)\b", text, re.I):
        mode = "UNKNOWN"
    if mode == "ACTUAL" and not PAST.search(text):
        mode = "UNKNOWN"
    return "UNKNOWN", mode, text


def physical_pairs(scope, entity=""):
    if not PHYSICAL_COUNT.search(scope):
        return []
    matches = list(QUANTITY.finditer(scope))
    # Model/brand modifiers come from the literal entity, never a name list.
    if entity and not re.search(UNITS + r"$", entity, re.I):
        branded = re.compile(r"\b(?P<amount>" + AMOUNT + r")\s+" + re.escape(entity) + r"\s+(?P<unit>" + UNITS + r")\b", re.I)
        matches.extend(branded.finditer(scope))
    return [m for m in matches
            if not re.search(r"[$€£¥]\s*$|\b(?:USD|EUR|GBP|JPY)\s*$", scope[:m.start()])]


def buyer_matches(claim, scope):
    party = re.escape(claim)
    patterns = (r"\b" + party + r"\s+(?:(?:has|have)\s+)?(?:placed|signed|awarded|secured)\b.{0,35}\b(?:orders?|purchase contract)\b",
                r"\b" + party + r"\s+(?:(?:has|have)\s+)?(?:ordered|purchased|bought|agreed to purchase)\b",
                r"\b(?:delivered|shipped|sold|supplied)\b.{0,80}\bto\s+" + party + r"\b",
                r"\b(?:orders?|purchase contract)\b.{0,50}\bfrom\s+" + party + r"\b")
    return [m for pattern in patterns for m in re.finditer(pattern, scope, re.I)]


def field_modality(fact, scope, entity=""):
    if fact["field"] == "region":
        if NEGATION.search(scope):
            return "NEGATED"
        regions = region_constructions(entity, scope)
        if len(regions) == 1 and re.search(r"\bto\s+(?:advance|support|accelerate|enable)\b", scope[:regions[0].start()], re.I):
            return "PLAN"  # Intended deployment region is not completed supply.
    if fact["field"] in ("quantity", "unit"):
        matches = [m for m in physical_pairs(scope, entity) if fact["value"].casefold() in
                   (m["amount"].casefold(), m[0].casefold(), m["unit"].casefold())]
    elif fact["field"] == "customer_group":
        matches = buyer_matches(fact["value"], scope)
    else:
        matches = []
    # A future shipment or pending qualification after a signed order cannot
    # turn the already signed buyer/quantity into a merely planned purchase.
    return modality(scope[:matches[0].end()]) if len(matches) == 1 else modality(scope)


def fact_support(item, fact, scope):
    field, claim = fact["field"], fact["value"]
    entity = item["entity"]["value"] or ""
    mode = field_modality(fact, scope, entity)
    if field == "product":
        return (item["kind"] in PHYSICAL and claim == item["entity"]["value"]), "PRODUCT_IDENTITY"
    if item["kind"] not in PHYSICAL:
        return False, "NONPHYSICAL_ENTITY"
    if mode == "NEGATED":
        return False, "NEGATED_FIELD_RELATION"
    if field == "quantity":
        if MONEY.search(claim):
            return False, "FINANCIAL_AMOUNT_NOT_PHYSICAL_QUANTITY"
        for match in physical_pairs(scope, entity):
            if claim.casefold() in (match["amount"].casefold(), match[0].casefold()):
                return True, "LITERAL_PHYSICAL_COUNT_OR_CAPACITY"
        return False, "NO_PRODUCT_QUANTITY_UNIT_PAIR"
    if field == "unit":
        return any(claim.casefold() == m["unit"].casefold() for m in physical_pairs(scope, entity)), "PHYSICAL_UNIT_REQUIRED"
    if field == "customer_group":
        return mode == "ACTUAL" and bool(buyer_matches(claim, scope)), "ACTUAL_PRODUCT_BUYER_RELATION_REQUIRED"
    if field == "supply_pool":
        party = re.escape(claim)
        patterns = (r"\b" + party + r"\s+(?:is|are)\s+(?:a |an |the )?(?:qualified|certified|eligible)\s+(?:supplier|manufacturer|producer)\b",
                    r"\b" + party + r"\s+(?:(?:has|have)\s+)?(?:passed|completed|received|achieved)\s+(?:customer |product |production )?(?:qualification|certification|approval)\b")
        return mode == "ACTUAL" and any(re.search(p, scope, re.I) for p in patterns), "ACTUAL_PRODUCT_QUALIFICATION_REQUIRED"
    if field == "specification":
        if claim in entity:
            return True, "EXPLICIT_PRODUCT_NAME_SPECIFICATION"
        rating = re.search(r"\b(?:rated|rating|nominal|voltage|each|per (?:unit|product))\b", scope, re.I)
        aggregate = re.search(r"\b(?:production capacity|annual output|factory capacity|plant capacity)\b", scope, re.I)
        if aggregate and not rating:
            return False, "AGGREGATE_CAPACITY_NOT_PRODUCT_SPECIFICATION"
        return bool(SPEC.search(claim) or rating and re.search(r"\b\d+(?:\.\d+)?\s*(?:MW|GW|kWh|V|nm|GHz)\b", claim)), "EXPLICIT_PRODUCT_SPECIFICATION"
    if field == "region":
        if MONEY.search(claim) or re.search(r"\d", claim) or TIME_WORDS.search(claim):
            return False, "NON_GEOGRAPHIC_VALUE"
        constructions = region_constructions(entity, scope)
        if len(constructions) == 1 and constructions[0]["region"] == claim:
            return True, "EXPLICIT_GEOGRAPHIC_PRODUCT_CONSTRUCTION"
        for match in re.finditer(r"\b(?:in|for|across|within|at|to|from)\s+(?:the )?" + re.escape(claim) + r"\b", scope, re.I):
            prefix = scope[:match.start()]
            corporate = [m.start() for m in re.finditer(r"\b(?:headquartered|headquarters|office|incorporated|registered)\b", prefix, re.I)]
            product = [m.start() for m in re.finditer(r"\b(?:manufactur\w*|produc\w*|production|deploy\w*|deliver\w*|ship\w*|ordered)\b", prefix, re.I)]
            if not corporate or product and product[-1] > corporate[-1]:
                return True, "EXPLICIT_PRODUCT_REGION"
        return False, "UNPROVEN_PRODUCT_REGION_OR_CORPORATE_LOCATION"
    if field == "period":
        return bool(physical_pairs(scope, entity) and re.search(r"\b(?:per|each|annual|monthly|quarterly|year|month|quarter)\b", claim, re.I)), "PHYSICAL_QUANTITY_PERIOD_REQUIRED"
    if field == "need_time":
        return bool(re.search(r"\b(?:delivery|deliveries|needed|required|due)\b.{0,30}\b(?:by|in|before|on|for)\b.{0,25}" + re.escape(claim), scope, re.I)), "CUSTOMER_NEED_OR_DELIVERY_DATE_REQUIRED"
    if field == "ready_time":
        return bool(re.search(r"\b(?:ready|available|operational|production (?:starts|begins)|start production)\b.{0,25}\b(?:by|in|from|on)\b.{0,25}" + re.escape(claim), scope, re.I)), "SUPPLY_READINESS_DATE_REQUIRED"
    if field == "lead_time":
        return bool(re.search(r"\blead times?\b.{0,65}" + re.escape(claim) + r"|\bdelivery (?:takes|within)\b.{0,25}" + re.escape(claim), scope, re.I)), "LEAD_TIME_NOT_DELAY_DURATION"
    if field == "relief":
        return bool(re.search(EVENTS["RELIEF"], scope, re.I)), "EXPLICIT_RELIEF_REQUIRED"
    if field == "alternative":
        return bool(re.search(r"\b(?:substitute for|alternative to|replaced by|can replace)\b", scope, re.I)), "EXPLICIT_ALTERNATIVE_REQUIRED"
    return False, "UNSUPPORTED_FIELD_MEANING"


def semantic_reading(verified):
    item = deepcopy(verified)
    model = {key: item[key] for key in ("kind", "role", "actuality")}
    item["kind"], kind_rule = identity(item)
    item["role"], item["actuality"], event_scope = event_reading(item)
    physical = item["kind"] in PHYSICAL and item["entity"]["value"] is not None
    item["target"] = {key: None for key in FIELDS}
    if physical:
        item["target"]["product"] = item["entity"]
    audit, decisions = [], []
    for fact in item["facts"]:
        if fact["value"] is None:
            decisions.append({"field": fact["field"], "status": "UNKNOWN", "reason": "MISSING_SOURCE_FACT"})
            continue
        scope = fact_scope(item, fact)
        accepted, reason = fact_support(item, fact, scope) if scope else (False, "UNPROVEN_PRODUCT_CLAUSE_RELATION")
        decisions.append({"field": fact["field"], "status": "ADOPTED" if accepted else "UNKNOWN",
                          "reason": reason, "actuality": field_modality(fact, scope, item["entity"]["value"] or "") if scope else "UNKNOWN"})
        if accepted:
            fact["semantic_actuality"] = field_modality(fact, scope, item["entity"]["value"] or "")
            if fact["field"] in FIELDS:
                item["target"][fact["field"]] = fact
        else:
            audit.append({"field": fact["field"], "reason": reason, "source_fact": deepcopy(fact)})
            fact.update(value=None, quote="", start=0, end=0, reference=None)
    item.update(model_classification=model, semantic_policy_version=VERSION, semantic_review=audit,
                semantic_checks={"kind": kind_rule, "field_decisions": decisions,
                    "physical_event_support": item["role"] != "UNKNOWN",
                    "role_retained": item["role"] != "UNKNOWN", "event_scope": event_scope,
                    "status": "LIMITED_RULE_CHECKS_NOT_GENERAL_SEMANTIC_VERIFICATION"},
                physical_exploration_lead=physical, semantic_status="UNKNOWN_REQUIRES_REVIEW",
                s_stage="UNKNOWN", forecast_candidate=False)
    return item
