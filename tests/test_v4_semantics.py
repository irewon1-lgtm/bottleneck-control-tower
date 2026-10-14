"""Stage 3 guard cases. Authored examples are separate from saved real responses."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from bct.v4.free_ai import Router, source_input, validate_reading
from bct.v4.store import Ledger
from test_v4_free_ai import ENV, Fake, config, document, router


def proposal(body, entity, facts=(), kind="PHYSICAL_PRODUCT", role="UNKNOWN", actuality="ACTUAL"):
    return {"items": [{"kind": kind, "role": role, "actuality": actuality,
        "context": {"quote": body}, "entity": {"value": entity, "quote": body if entity else ""},
        "facts": [{"field": field, "value": value, "quote": body if value is not None else ""}
                  for field, value in facts]}]}


def check(body, entity, facts=(), **kw):
    doc = document(body=body)
    result = validate_reading(json.dumps(proposal(body, entity, facts, **kw)), doc, source_input(doc, config(), ENV))
    assert result["source_status"] == "PASS"
    item = result["items"][0]
    assert item["s_stage"] == "UNKNOWN" and not item["forecast_candidate"]
    assert item["semantic_status"] == "UNKNOWN_REQUIRES_REVIEW"
    return item


def value(item, name):
    return next((f["value"] for f in item["facts"] if f["field"] == name), None)


@pytest.mark.parametrize("entity,money,recipient,body", [
    ("advanced light-water SMRs", "$800 million", "TVA and Holtec", "The department awarded $800 million to TVA and Holtec to advance deployment of advanced light-water SMRs."),
    ("battery cells", "€60 million", "VoltWorks", "The ministry granted €60 million to VoltWorks for developing battery cells."),
    ("optical transceivers", "USD 12 million", "Photon Labs", "Photon Labs received USD 12 million in subsidies for optical transceivers."),
    ("industrial heat pumps", "250 million", "Thermo Labs", "Thermo Labs received £250 million in funding for industrial heat pumps."),
])
def test_funding_is_neither_physical_quantity_nor_proven_customer(entity, money, recipient, body):
    item = check(body, entity, (("quantity", money), ("customer_group", recipient)), role="SUPPLY_INCREASE")
    assert value(item, "quantity") is None and value(item, "customer_group") is None
    assert item["target"]["customer_group"] is None and item["role"] == "UNKNOWN"
    assert len(item["semantic_review"]) == 2
    assert item["physical_exploration_lead"]


@pytest.mark.parametrize("body,entity,field,claim,expected", [
    ("Forge Motors placed an order for 24 industrial heat pumps.", "industrial heat pumps", "customer_group", "Forge Motors", "Forge Motors"),
    ("VoltWorks delivered 40 battery cells to Grid Co.", "battery cells", "customer_group", "Grid Co", "Grid Co"),
    ("Photon Labs secured a purchase contract from Cloud Co for optical transceivers.", "optical transceivers", "customer_group", "Cloud Co", "Cloud Co"),
    ("Forge Motors plans to order industrial heat pumps.", "industrial heat pumps", "customer_group", "Forge Motors", None),
    ("Forge Motors did not sign an order for industrial heat pumps.", "industrial heat pumps", "customer_group", "Forge Motors", None),
    ("Photon Labs established a strategic partnership with Cloud Co for optical transceivers.", "optical transceivers", "customer_group", "Cloud Co", None),
    ("Grid Co bought optical transceivers; VoltWorks received a grant for battery cells.", "battery cells", "customer_group", "Grid Co", None),
    ("Alloy Co is a qualified supplier of battery cells.", "battery cells", "supply_pool", "Alloy Co", "Alloy Co"),
    ("Alloy Co manufactures battery cells.", "battery cells", "supply_pool", "Alloy Co", None),
    ("Alloy Co is not yet a qualified supplier of battery cells.", "battery cells", "supply_pool", "Alloy Co", None),
    ("Alloy Co expects to become a qualified supplier of battery cells.", "battery cells", "supply_pool", "Alloy Co", None),
    ("Alloy Co is a qualified supplier of optical transceivers; VoltWorks produces battery cells.", "battery cells", "supply_pool", "Alloy Co", None),
    ("Forge Motors signed an order for battery cells that will be delivered in 2028.", "battery cells", "customer_group", "Forge Motors", "Forge Motors"),
    ("Forge Motors signed an order for battery cells that are not yet customer-qualified.", "battery cells", "customer_group", "Forge Motors", "Forge Motors"),
])
def test_customer_and_qualified_supplier_require_product_relations(body, entity, field, claim, expected):
    item = check(body, entity, ((field, claim),))
    assert value(item, field) == expected and (item["target"][field] or {}).get("value") == expected


@pytest.mark.parametrize("body,entity,qty,unit,expected_qty,expected_unit", [
    ("VoltWorks produced 40 battery cells.", "battery cells", "40", "cells", "40", "cells"),
    ("Photon Labs shipped 2 million optical transceivers.", "optical transceivers", "2 million", "transceivers", "2 million", "transceivers"),
    ("The production capacity for industrial heat pumps expanded to 2000 units per year.", "industrial heat pumps", "2000", "units", "2000", "units"),
    ("The factory produced 40 units of battery cells.", "battery cells", "40", "units", "40", "units"),
    ("Battery cells research employed 40 workers.", "Battery cells", "40", "workers", None, None),
    ("Photon Labs granted $2 million for optical transceivers.", "optical transceivers", "2 million", "million", None, None),
    ("VoltWorks invested $5 million and delivered 30 battery cells.", "battery cells", "30", "cells", "30", "cells"),
    ("Optical transceivers cost $40 each.", "Optical transceivers", "$40", "each", None, None),
    ("Battery cells revenue grew by 20%.", "Battery cells", "20%", "%", None, None),
    ("Supplier delivered 20 NovaLT16 turbines.", "NovaLT16", "20", "turbines", "20", "turbines"),
    ("Supplier shipped 300 AX900 chips.", "AX900", "300", "chips", "300", "chips"),
    ("Production of battery cells reached 2 GWh per year.", "battery cells", "2", "GWh", "2", "GWh"),
])
def test_quantities_need_physical_units_and_correct_scope(body, entity, qty, unit, expected_qty, expected_unit):
    item = check(body, entity, (("quantity", qty), ("unit", unit)))
    assert value(item, "quantity") == expected_qty and value(item, "unit") == expected_unit


@pytest.mark.parametrize("body,entity,role,expected_role,actuality", [
    ("Forge Motors signed an order for industrial heat pumps.", "industrial heat pumps", "DEMAND_INCREASE", "DEMAND_INCREASE", "ACTUAL"),
    ("Forge Motors plans to order industrial heat pumps.", "industrial heat pumps", "DEMAND_INCREASE", "UNKNOWN", "PLAN"),
    ("Forge Motors expects orders for industrial heat pumps to increase.", "industrial heat pumps", "DEMAND_INCREASE", "DEMAND_INCREASE", "FORECAST"),
    ("Production of optical transceivers decreased by 20%.", "optical transceivers", "SUPPLY_DECREASE", "SUPPLY_DECREASE", "ACTUAL"),
    ("Production of battery cells was delayed by six months.", "battery cells", "SUPPLY_DELAY", "SUPPLY_DELAY", "ACTUAL"),
    ("The production capacity of battery cells expanded by 20%.", "battery cells", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "ACTUAL"),
    ("The production capacity of battery cells did not expand.", "battery cells", "SUPPLY_INCREASE", "UNKNOWN", "NEGATED"),
    ("The supplier has not delayed production of optical transceivers.", "optical transceivers", "SUPPLY_DELAY", "UNKNOWN", "NEGATED"),
    ("Lead times for industrial heat pumps shortened from eight weeks to four weeks.", "industrial heat pumps", "RELIEF", "RELIEF", "ACTUAL"),
    ("Inventory of optical transceivers increased.", "optical transceivers", "RELIEF", "RELIEF", "ACTUAL"),
    ("Lead times for industrial heat pumps have not shortened.", "industrial heat pumps", "RELIEF", "UNKNOWN", "NEGATED"),
    ("The company expects a surplus of battery cells.", "battery cells", "RELIEF", "RELIEF", "FORECAST"),
    ("VoltWorks received funding to expand production of battery cells.", "battery cells", "SUPPLY_INCREASE", "UNKNOWN", "ACTUAL"),
    ("Photon Labs announced a strategic partnership for optical transceivers.", "optical transceivers", "DEMAND_INCREASE", "UNKNOWN", "ACTUAL"),
    ("Production of optical transceivers expanded; battery cells research received a grant.", "battery cells", "SUPPLY_INCREASE", "UNKNOWN", "ACTUAL"),
    ("The company announced plans to expand battery cells production.", "battery cells", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "PLAN"),
    ("Lead times for industrial heat pumps increased.", "industrial heat pumps", "RELIEF", "SUPPLY_DELAY", "ACTUAL"),
    ("Inventory of optical transceivers fell.", "optical transceivers", "RELIEF", "UNKNOWN", "ACTUAL"),
    ("Delivery of battery cells is no longer delayed.", "battery cells", "SUPPLY_DELAY", "RELIEF", "ACTUAL"),
    ("Delivery of battery cells is no longer delayed.", "battery cells", "RELIEF", "RELIEF", "ACTUAL"),
    ("VoltWorks received a grant and production capacity of battery cells expanded by 20%.", "battery cells", "SUPPLY_INCREASE", "SUPPLY_INCREASE", "ACTUAL"),
    ("Photon Labs signed a research contract for optical transceivers.", "optical transceivers", "DEMAND_INCREASE", "UNKNOWN", "ACTUAL"),
])
def test_events_are_product_scoped_and_distinguish_modality(body, entity, role, expected_role, actuality):
    item = check(body, entity, role=role)
    assert (item["role"], item["actuality"]) == (expected_role, actuality)


@pytest.mark.parametrize("body,entity,field,claim,expected", [
    ("Forge Motors ordered industrial heat pumps for delivery by March 2028.", "industrial heat pumps", "need_time", "March 2028", "March 2028"),
    ("Production of battery cells will be ready by June 2028.", "battery cells", "ready_time", "June 2028", "June 2028"),
    ("The lead time for optical transceivers is six months.", "optical transceivers", "lead_time", "six months", "six months"),
    ("Production capacity for battery cells is 2000 units per year.", "battery cells", "period", "per year", "per year"),
    ("The ministry awarded funding for battery cells on March 2028.", "battery cells", "need_time", "March 2028", None),
    ("Photon Labs announced an investment for optical transceivers in June 2028.", "optical transceivers", "ready_time", "June 2028", None),
    ("Delivery of battery cells was delayed by six months.", "battery cells", "lead_time", "six months", None),
    ("The funding programme for industrial heat pumps was launched in 2025.", "industrial heat pumps", "period", "2025", None),
    ("The customer ordered Class 8 trucks for deployment in Germany.", "Class 8 trucks", "specification", "Class 8", "Class 8"),
    ("The customer ordered Class 8 trucks for deployment in Germany.", "Class 8 trucks", "region", "Germany", "Germany"),
    ("Class 8 trucks are not intended for Germany.", "Class 8 trucks", "region", "Germany", None),
])
def test_time_specification_and_region_require_the_right_relation(body, entity, field, claim, expected):
    item = check(body, entity, ((field, claim),))
    assert value(item, field) == expected
    if field in item["target"]:
        assert (item["target"][field] or {}).get("value") == expected


@pytest.mark.parametrize("entity,kind,expected", [
    ("battery cells", "PROJECT", "PRODUCT_FAMILY"),
    ("industrial heat pumps", "PROJECT", "PRODUCT_FAMILY"),
    ("photolithography equipment", "PROJECT", "MANUFACTURING_EQUIPMENT"),
    ("300mm wafer production slots", "PROJECT", "PRODUCTION_SLOT"),
    ("Solar Factory Expansion Project", "PHYSICAL_PRODUCT", "PROJECT"),
    ("Item 7.01.", "UNKNOWN", "DISCLOSURE_HEADING"),
    ("company", "UNKNOWN", "GENERAL_EXPRESSION"),
])
def test_product_equipment_slot_project_and_heading_are_distinct(entity, kind, expected):
    item = check("The announcement mentions " + entity, entity, kind=kind)
    assert item["kind"] == expected
    if expected in ("PROJECT", "GENERAL_EXPRESSION", "DISCLOSURE_HEADING"):
        assert item["target"]["product"] is None and not item["physical_exploration_lead"]


def test_absent_information_stays_unknown_and_does_not_become_supply():
    item = check("The report mentions optical transceivers.", "optical transceivers")
    assert item["target"]["product"]["value"] == "optical transceivers"
    assert set(item["target"]) == {"product", "specification", "region", "customer_group", "supply_pool"}
    assert all(item["target"][key] is None for key in item["target"] if key != "product")
    assert item["role"] == "UNKNOWN" and item["physical_exploration_lead"]


def test_actual_order_quantity_is_not_relabelled_by_future_shipping_or_unqualified_supplier():
    item = check("Forge Motors signed an order for 24 battery cells that will ship in 2028.",
                 "battery cells", (("quantity", "24"), ("unit", "cells"), ("customer_group", "Forge Motors")), role="DEMAND_INCREASE")
    assert item["role"] == "DEMAND_INCREASE" and item["actuality"] == "ACTUAL"
    assert value(item, "quantity") == "24" and value(item, "customer_group") == "Forge Motors"
    assert all(f["semantic_actuality"] == "ACTUAL" for f in item["facts"])
    assert item["target"]["supply_pool"] is None


@pytest.mark.parametrize("body,entity,field,claim,expected", [
    ("Inventory of battery cells increased.", "battery cells", "relief", "increased", "increased"),
    ("Funding for battery cells increased.", "battery cells", "relief", "increased", None),
    ("Optical transceivers can be replaced by copper cables.", "Optical transceivers", "alternative", "copper cables", "copper cables"),
    ("The report discusses optical transceivers and copper cables.", "optical transceivers", "alternative", "copper cables", None),
    ("The company headquartered in Germany manufactures battery cells in France.", "battery cells", "region", "Germany", None),
    ("The company headquartered in Germany manufactures battery cells in France.", "battery cells", "region", "France", "France"),
    ("Production capacity for wind turbines is 15 MW per year.", "wind turbines", "specification", "15 MW", None),
    ("The wind turbines have a rated power of 15 MW each.", "wind turbines", "specification", "15 MW", "15 MW"),
])
def test_relief_alternative_and_target_attributes_do_not_borrow_business_facts(body, entity, field, claim, expected):
    item = check(body, entity, ((field, claim),))
    assert value(item, field) == expected


@pytest.mark.parametrize("body,entity,expected", [
    ("Photon Labs signed a contract to research optical transceivers.", "optical transceivers", "UNKNOWN"),
    ("Thermo Labs signed a contract for feasibility studies for industrial heat pumps.", "industrial heat pumps", "UNKNOWN"),
    ("Photon Labs signed a supply contract to deliver 20 optical transceivers.", "optical transceivers", "DEMAND_INCREASE"),
])
def test_business_services_contract_is_not_a_product_order(body, entity, expected):
    item = check(body, entity, role="DEMAND_INCREASE")
    assert item["role"] == expected and item["actuality"] == "ACTUAL"


def test_saved_real_response_gold_known_errors_and_unread_scope():
    fixture = json.loads((Path(__file__).parent / "fixtures/v4_stage3_official_source.json").read_text())
    gold = json.loads((Path(__file__).parent / "fixtures/v4_stage3_gold.json").read_text())
    doc = fixture["document"]
    selected = fixture["selected_input"]
    result = validate_reading(fixture["response_text"], doc, selected)
    assert result["source_status"] == "PASS" and len(result["items"]) == 3
    for answer in gold["items"]:
        item = result["items"][answer["input_item_index"]]
        assert item["context"]["quote"] == answer["source_quote"]
        for field, expected in answer["expected"].items():
            actual = item["entity"]["value"] if field == "entity" else item[field] if field in ("kind", "role", "actuality") else value(item, field)
            assert actual == expected, (field, actual, expected)
    assert result["coverage"]["selected_characters"] == 600
    assert result["coverage"]["unread_characters"] == len(doc["body"]) - 600
    assert result["coverage"]["unread_ranges"] == [{"start": 0, "end": 5905}, {"start": 6505, "end": len(doc["body"])}]


def test_semantic_holds_persist_when_cached_real_shape_is_reopened(tmp_path):
    body = "VoltWorks received €60 million in grants for battery cells."
    data = proposal(body, "battery cells", (("quantity", "€60 million"), ("customer_group", "VoltWorks")))
    doc = document(body=body)
    fake = Fake({"groq": {"text": json.dumps(data), "usage": {"total_tokens": 30}, "headers": {}}})
    ledger = Ledger(tmp_path); ledger.capture(doc)
    with ledger.worker():
        first = router(ledger, fake).read(doc)
    ledger.close(); ledger = Ledger(tmp_path)
    with ledger.worker():
        second = router(ledger, fake, run="restart").read(doc)
    assert second["cached"] and first["status"] == second["status"] == "PASS"
    assert fake.calls == ["groq"]
    item = second["result"]["items"][0]
    assert value(item, "quantity") is None and item["target"]["customer_group"] is None
    assert len(item["semantic_review"]) == 2 and item["s_stage"] == "UNKNOWN"
    assert json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='API_RESPONSE'").fetchone()[0])["text"] == json.dumps(data)
    ledger.close()
