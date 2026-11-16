"""Adversarial tests for S5 quantitative evidence; no network, no CPU model."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s5_quantitative_capacity_audit as q

MANIFEST=ROOT/"config/bct-s5-quantitative-originals-20261116.json"

def manifest():
    return json.loads(MANIFEST.read_text())

def prior():
    return {"format":"bct-s5-public-primary-original-crosscheck-v1",
            "case_count":8,"attempted_public_primary_urls":8,
            "fetched_bodies":8,"candidate_or_LIVE_writes":0,
            "strict_eligible_supply_demand_pairs":0,
            "no_source_text_exported":True,
            "S4_11_originals_or_private_epoch_modified":False}

STDN_TEXT="""
Standard Nuclear, Inc. quarterly report September 30, 2026.
On August 26, 2026, Standard Nuclear entered into a fuel supply agreement
with Antares Nuclear, Inc. for the fabrication and delivery of one MTU (1,000 kgU)
of HALEU TRISO fuel, with an option for Antares to purchase up to seven
additional MTU (7,000 kgU). Antares is required to take delivery of the firm
quantity by December 31, 2030. The option is exercisable in one MTU increments
by written notice no later than December 31, 2027, with deliveries of exercised
quantities beginning as early as 2028.
Facility commissioning and production ramp-up.
The Company targets receiving DOE authorization to operate at both SN-TN and
SN-ID in February 2027.
The Company’s SN-0 facility in Oak Ridge produces TRISO fuel with capacity of
up to 0.5 MTU annually. SN-0 operates at just above 25% of its 0.5 MTU annual
capacity, reflecting early stage customer deliveries.
Feedstock availability: Our ability to perform under customer arrangements depends
in part on the availability and timely receipt of enriched uranium feedstock.
The table below details our Production Capacity as of September 30, 2026:
Module Throughput Capacity 0.5 MTU/y (1)
Building Throughput Capacity 5.5 MTU/y (2)
Process Yield % 63.3 (3)
Richland SN-F facility plans initial capacity of approximately one MTU annually.
"""
CENTRUS_TEXT="""
Centrus Energy Corp. News Release:
Centrus Reports Third Quarter 2026 Results.
Grew contingent Low-Enriched Uranium and High-Assay Low-Enriched Uranium
enrichment backlog to $5.4 billion.
Enriching HALEU for the commercial market from existing 16-centrifuge cascade.
Backlog. The current DOE budget proposed for fiscal year 2027 does not include
further funding for the operation of the HALEU cascade.
"""

def raw_body(text):
    return ("<html><body><h1>Public original research case</h1><main>"+
            "<p>"+text+"</p>"+"<p>Other issuer original context facts and records.</p>"*30+
            "</main></body></html>").encode()

def cases_from_fake_text():
    m=manifest()
    t={"standard_2026q3_sec_10q":STDN_TEXT,
       "centrus_2026q3_issuer":CENTRUS_TEXT}
    return [q.extract_case(s,raw_body(t[s["id"]]),final=s["url"]) for s in m["sources"]]

class TestQuantitativeEvidence(unittest.TestCase):
    def test_two_pinned_official_public_urls_only(self):
        m=manifest()
        self.assertEqual(len(q.validate_manifest(m)),2)
        self.assertEqual({x["id"] for x in m["sources"]},q.SOURCE_IDS)

    def test_live_private_or_changed_original_url_rejected(self):
        m=manifest()
        m["sources"][0]["url"]="https://127.0.0.1/secret"
        m["sources"][0]["host"]="127.0.0.1"
        with self.assertRaisesRegex(ValueError,"PRIVATE_ADDRESS"):q.validate_manifest(m)
        m=manifest();m["sources"][0]["url"]+="?latest=1"
        with self.assertRaisesRegex(ValueError,"URL_OR_HOST"):q.validate_manifest(m)
        m=manifest();m["sources"][0]["url"]="/faked-report"
        with self.assertRaisesRegex(ValueError,"URL_OR_HOST"):q.validate_manifest(m)
        m=manifest();m["mode"]="LIVE"
        with self.assertRaisesRegex(ValueError,"MANIFEST_CONTRACT_CHANGED"):q.validate_manifest(m)
        m=manifest();m["sources"][0]["url"]="https://ir.standardnuclear.com/other.html"
        with self.assertRaisesRegex(ValueError,"CHANGED_PUBLIC_ORIGINAL_URL"):q.validate_manifest(m)

    def test_fake_original_has_1_mtu_firm_and_7_option_not_8_firm(self):
        m=manifest()
        report=q.derive(m,prior(),cases_from_fake_text())
        self.assertEqual(report["firm_contract_cumulative_MTU_by_2030"],1)
        self.assertEqual(report["Antares_customer_optional_MTU_not_firm"],7)
        self.assertEqual(report["Antares_firm_latest_delivery_date"],"2030-12-31")
        self.assertEqual(report["Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30"],0.5)
        self.assertEqual(report["Standard_building_envelope_MTU_per_year_not_operational"],5.5)
        self.assertEqual(report["Standard_overall_process_yield_pct_not_second_multiplier"],63.3)
        self.assertEqual(report["new_early_candidates"],0)
        self.assertEqual(report["LIVE_writes"],0)
        self.assertEqual(report["confirmed_shortage"],"NOT_ESTABLISHED")

    def test_uncertain_calendar_never_extrapolates_1_by_2030_into_2027_firm(self):
        out=q.derive(manifest(),prior(),cases_from_fake_text())
        self.assertEqual(set(out["annual_comparison"]),set(q.PERIODS))
        for item in out["annual_comparison"].values():
            self.assertEqual(item["Antares_firm_TRISO_deliveries_MTU"],"UNKNOWN")
            self.assertEqual(item["qualified_customer_eligible_unreserved_TRISO_output_MTU"],"UNKNOWN")
            self.assertEqual(item["same_scope_physical_gap_MTU"],"UNKNOWN")
        self.assertIn("CUSTOMER_FIRM_YEAR_BY_YEAR_DELIVERY_REQUIREMENT",
                      out["missing_required_evidence"])

    def test_no_capacity_source_confirmation_without_correct_subsection(self):
        t=STDN_TEXT.replace("Module Throughput Capacity 0.5 MTU/y (1)",
                            "Module Throughput Capacity UNKNOWN")
        r=q.extract_case(manifest()["sources"][0],raw_body(t),
                         final=manifest()["sources"][0]["url"])
        lookup={x["fact_id"]:x for x in r["fact_receipts"]}
        self.assertEqual(lookup["STDN_INSTALLED_AUTHORIZED_THROUGHPUT_MTU_Y"]["value"],"UNKNOWN")
        self.assertEqual(lookup["STDN_BUILDING_THEORETICAL_MTU_Y"]["value"],5.5)
        self.assertEqual(q.bound_fact("Revenue 0.5 MTU/y, Module Throughput Capacity UNKNOWN",
                                       "Module Throughput Capacity",
                                       r"Module Throughput Capacity\s*0\.5\s*MTU\s*/\s*y",100),None)

    def test_unread_or_missing_independent_source_not_zero_physical_supply(self):
        m=manifest()
        cs=[q.extract_case(s,None,error="HTTP_403") for s in m["sources"]]
        out=q.derive(m,prior(),cs)
        self.assertEqual(out["official_originals_fetched"],0)
        self.assertEqual(out["firm_contract_cumulative_MTU_by_2030"],"UNKNOWN")
        self.assertEqual(out["confirmed_shortage"],"NOT_ESTABLISHED")
        self.assertEqual(out["new_early_candidates"],0)

    def test_reject_fake_typed_value_or_cross_issuer_receipt(self):
        m=manifest();cases=cases_from_fake_text()
        cases[0]["fact_receipts"][0]["value"]=8
        with self.assertRaisesRegex(ValueError,"CHANGED_TYPED_FACT"):q.derive(m,prior(),cases)
        cases=cases_from_fake_text()
        cases[0]["fact_receipts"][0]["fact_id"]="CENTRUS_OPERATING_CASCADE_COUNT"
        with self.assertRaisesRegex(ValueError,"FACT_DUPLICATE_OR_CROSS_SOURCE"):q.derive(m,prior(),cases)

    def test_prior_evidence_missing_or_mutated_fails_closed(self):
        m=manifest()
        p=prior();p["fetched_bodies"]=6
        with self.assertRaisesRegex(ValueError,"PREVIOUS_PUBLIC_PROOF"):
            q.derive(m,p,cases_from_fake_text())
        p=prior();p["candidate_or_LIVE_writes"]=1
        with self.assertRaisesRegex(ValueError,"PREVIOUS_PUBLIC_PROOF"):
            q.derive(m,p,cases_from_fake_text())

    def test_source_free_sqlite_new_process_and_tamper_fail(self):
        cs=cases_from_fake_text();r=q.derive(manifest(),prior(),cs)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"proof"
            q.save_and_verify(out,r,cs)
            check=q.fresh_readback(out)
            self.assertEqual(check["originals"],2)
            self.assertTrue(check["status"].startswith("PASS"))
            with self.assertRaisesRegex(ValueError,"NO_OVERWRITE_ALLOWED"):
                q.save_and_verify(out,r,cs)
            (out/"research.sqlite3").write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError,"REQUERY_SQLITE_SHA"):
                q.fresh_readback(out)

if __name__=="__main__":
    unittest.main()
