"""S5 public supplier primary source and economic-event independence regressions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s5_supplier_fact_followon as s5

M=ROOT/"config/bct-s5-supplier-official-followon-20261116.json"

def manifest():
    return json.loads(M.read_text())
def prior():
    return {
      "format":"bct-s5-typed-quantitative-original-check-v1",
      "target_id":"unobligated-haleu-us-qualified-supply",
      "official_originals_fetched":1,
      "firm_contract_cumulative_MTU_by_2030":1,
      "Standard_operational_reported_module_MTU_per_year_as_of_2026_09_30":0.5,
      "Standard_building_envelope_MTU_per_year_not_operational":5.5,
      "new_early_candidates":0,"LIVE_writes":0,
      "confirmed_shortage":"NOT_ESTABLISHED",
      "source_text_exported":False,
      "annual_comparison":{
        str(y):{"same_scope_physical_gap_MTU":"UNKNOWN"}
        for y in range(2027,2031)}}
def rendered(src,sentences):
    html=("<html><article><h1>"+src["title"]+"</h1><time>"+src["date_markers"][0]+
          "</time><h2>"+src["issuer_marker"]+"</h2><section>"+sentences+"</section>"+
          "<p>Background source version archived for public research and source verification.</p>"*20+
          "</article></html>")
    return html.encode()
def cases():
    sources=s5.validate_manifest(manifest())
    ctext=("Centrus Energy Corp. continued using its existing 16-centrifuge cascade. "
           "Grew contingent Low-Enriched Uranium (LEU) and High-Assay Low-Enriched "
           "Uranium (HALEU) enrichment backlog to $5.4 billion. "
           "The current DOE budget proposed for fiscal year 2027 does not include "
           "further funding for the operation of the HALEU cascade.")
    btext=("BWX Technologies, Inc. announced an initial allocation of 1 MTU. "
           "Fuel deliveries will use future task orders that define specific "
           "quantities, delivery schedules and technical requirements.")
    return [s5.read_source(s,rendered(s,ctext if "centrus" in s["id"] else btext),
                           final=s["url"]) for s in sources]

class IndependentSupplierFactsTest(unittest.TestCase):
    def test_exact_3_pinned_public_source_cohort(self):
        self.assertEqual(len(s5.validate_manifest(manifest())),3)
        self.assertEqual(set(s5.PINNED),s5.SOURCE_IDS)
    def test_no_private_or_changed_public_endpoint(self):
        m=manifest();m["sources"][0]["url"]="https://127.0.0.1/a"
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_SOURCE_URL"):
            s5.validate_manifest(m)
        m=manifest();m["sources"][0]["url"]+="?q=secret"
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_SOURCE_URL"):
            s5.validate_manifest(m)
        m=manifest();m["cutoff"]="2028-11-16"
        with self.assertRaisesRegex(ValueError,"MANIFEST_OBJECTIVE"):
            s5.validate_manifest(m)
    def test_visible_title_date_issuer_and_located_facts_are_separate_from_strict_provenance(self):
        c=cases()
        self.assertTrue(all(x["status"]=="ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY" for x in c))
        self.assertTrue(all(x["strict_global_provenance"]=="NOT_INFERRED_FROM_URL" for x in c))
        self.assertTrue(any(f["fact_id"]=="CENTRUS_EXISTING_CASCADE_16" and f["value"]==16
                         for f in c[0]["facts"]))
        self.assertTrue(any(f["fact_id"]=="BWXT_ANTARES_INITIAL_ALLOCATION_1_MTU" and f["value"]==1
                         for f in c[2]["facts"]))
        self.assertNotIn("body",c[0])
        self.assertNotIn("raw",c[0])
        self.assertTrue(all(f["location"]["span_sha256"] for f in c[0]["facts"]
                            if f["state"]=="VISIBLE_SOURCE_SPAN_HASH_VERIFIED"))
    def test_copies_of_centrus_q3_do_not_make_two_economic_facts(self):
        out=s5.aggregate(manifest(),prior(),cases())
        self.assertEqual(out["centrus_same_disclosure_copies_not_independent_pair"],2)
        self.assertEqual(out["distinct_issuer_economic_events_with_evidence"],2)
        self.assertFalse(out["strict_pair_evaluated"])
        self.assertEqual(out["new_bottleneck_candidates"],0)
        self.assertEqual(out["centrus_cascade_machine_count"],16)
        self.assertEqual(out["centrus_fy2027_budget_operation_funding_not_included"],True)
        self.assertEqual(out["centrus_contingent_backlog_usd_billion"],5.4)
        self.assertEqual(out["bwxt_initial_contract_allocation_MTU_not_annual"],1)
    def test_absent_or_unverified_original_remains_unknown(self):
        items=[s5.read_source(x,None,error="HTTP_403") for x in manifest()["sources"]]
        result=s5.aggregate(manifest(),prior(),items)
        self.assertEqual(result["public_source_bodies_captured"],0)
        self.assertEqual(result["centrus_cascade_machine_count"],s5.UNKNOWN)
        self.assertEqual(result["bwxt_initial_contract_allocation_MTU_not_annual"],s5.UNKNOWN)
        self.assertFalse(result["strict_pair_evaluated"])
        self.assertEqual(result["LIVE_writes"],0)
    def test_lack_of_yearly_delivery_and_eligible_supply_never_becomes_zero(self):
        result=s5.aggregate(manifest(),prior(),cases())
        for name in ("2027_2030_customer_firm_annual_delivery_MTU",
                     "2027_2030_customer_eligible_unreserved_TRISO_output_MTU",
                     "2027_2030_demonstrated_demand_minus_supply_MTU"):
            self.assertEqual(result[name],{str(y):"UNKNOWN" for y in range(2027,2031)})
    def test_no_impersonated_case_or_changed_positive_value(self):
        c=cases();c[0]["issuer"]="Other"
        with self.assertRaisesRegex(ValueError,"SOURCE_IDENTITY"):
            s5.aggregate(manifest(),prior(),c)
        c=cases()
        c[0]["facts"][0]["value"]=100
        with self.assertRaisesRegex(ValueError,"IMPUTED_OR_WRONG_UNIT"):
            s5.aggregate(manifest(),prior(),c)
        c=cases()
        c[2]["facts"][0]["fact_id"]="CENTRUS_EXISTING_CASCADE_16"
        with self.assertRaisesRegex(ValueError,"SOURCE_FACT_SET_CHANGED"):
            s5.aggregate(manifest(),prior(),c)
    def test_prior_s5_q3_artifact_must_be_exact_without_early_candidate(self):
        old=prior();old["firm_contract_cumulative_MTU_by_2030"]=8
        with self.assertRaisesRegex(ValueError,"PRIOR_Q3"):
            s5.aggregate(manifest(),old,cases())
        old=prior();old["new_early_candidates"]=1
        with self.assertRaisesRegex(ValueError,"PRIOR_Q3"):
            s5.aggregate(manifest(),old,cases())
    def test_new_process_requery_and_tamper_rejection(self):
        c=cases();report=s5.aggregate(manifest(),prior(),c)
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/"out"
            saved=s5.persist(output,report,c)
            self.assertEqual(s5.requery(output)["cases"],3)
            self.assertTrue(saved["sql_sha256"])
            with self.assertRaisesRegex(ValueError,"NO_OVERWRITE"):
                s5.persist(output,report,c)
            (output/"source-free.sqlite3").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError,"SQLITE_SHA_CHANGED"):
                s5.requery(output)

if __name__=="__main__": unittest.main()
