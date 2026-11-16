"""S5 scoped 22-registered-TARGET disposition and S6 source-free handoff tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s5_22_target_disposition as d

def prior():
    from bct.objective_lock import stamp_export
    return stamp_export({
        "format":"bct-s5-supplier-facts-readonly-v1",
        "status":"PASS_READONLY_SOURCE_BOUND_RISK_AND_NONPROMOTION_CLASSIFICATION",
        "session5_final":"PARTIAL_NO_SAME_PERIOD_ELIGIBLE_UNRESERVED_SUPPLY_EVIDENCE",
        "public_source_bodies_captured":3,
        "verified_visible_public_originals":3,
        "verified_distinct_fact_count":8,
        "centrus_same_disclosure_copies_not_independent_pair":3,
        "strict_pair_evaluated":False,"actual_qualified_pair_count":"NOT_EVALUATED",
        "new_bottleneck_candidates":0,
        "model_API_calls":0,"private_epoch_writes":0,"LIVE_writes":0,
        "original_source_text_stored":False,
        "2027_2030_demonstrated_demand_minus_supply_MTU":{
            str(y):"UNKNOWN" for y in range(2027,2031)}
    })

class TestAll22BoundedReview(unittest.TestCase):
    def test_real_frozen_target_inventory_22_and_distinct_historical_sources(self):
        qa,h=d.checked_source(ROOT,d.QA_REL)
        t=d.validate_qa(qa)
        self.assertEqual(len(t),22)
        self.assertEqual(len({x["target_id"] for x in t}),22)
        self.assertEqual(qa["registered_official"]["unique_verified_originals"],27)
        self.assertTrue(len(h)==64)

    def test_existing_registration_patches_reconciled_without_unfounded_pair(self):
        r,files=d.discover_registered(ROOT)
        self.assertGreaterEqual(len(files),15)
        self.assertTrue(all(x["registration_sha256"] for v in r.values() for x in v))
        self.assertTrue(all(x["strict_claim"] is not True for v in r.values() for x in v))

    def test_all_22_are_explicitly_hold_not_qualified_or_rejected_or_deleted(self):
        summary,cases,files=d.review(ROOT,prior())
        self.assertEqual(summary["targets_reviewed"],22)
        self.assertEqual(summary["qualified"],0)
        self.assertEqual(summary["rejected"],0)
        self.assertEqual(summary["hold"],22)
        self.assertEqual(summary["full_10k_article_research_audit"],"NOT_PERFORMED")
        self.assertTrue(summary["s6_handoff_status"].startswith("READY_RESEARCH_HOLD_ONLY"))
        self.assertEqual(len({x["target_id"] for x in cases}),22)
        self.assertTrue(all(x["research_disposition"]=="HOLD"
                            and x["known_annual_deficit_measured"]=="UNKNOWN"
                            for x in cases))

    def test_legacy_future_and_emerging_are_preserved_not_promoted(self):
        s,cases,files=d.review(ROOT,prior())
        legacy={x["target_id"]:x for x in cases}
        self.assertEqual(legacy["large-gas-turbine-slots"]["prior_display_stage_2026_09_30"],"FUTURE")
        self.assertEqual(legacy["uk-regional-grid-connections"]["prior_display_stage_2026_09_30"],"EMERGING")
        self.assertEqual(legacy["large-gas-turbine-slots"]["research_disposition"],"HOLD")
        self.assertTrue(all(x["is_legacy_stage_proof"] is False for x in cases))

    def test_haleu_s5_progress_is_retained_without_qualifying_shortage(self):
        s,cases,files=d.review(ROOT,prior())
        h=next(x for x in cases if x["target_id"]=="unobligated-haleu-us-qualified-supply")
        self.assertEqual(h["s5_new_research"],"8_SOURCE_BOUND_FACTS_NO_ELIGIBLE_PAIR")
        self.assertFalse(h["source_independent_pair_verified"])
        self.assertFalse(h["qualified_unreserved_same_period_supply_verified"])
        self.assertEqual(h["research_disposition"],"HOLD")

    def test_source_proof_corruption_unread_or_wrong_count_fails_closed(self):
        p=prior();p["verified_distinct_fact_count"]=9
        with self.assertRaisesRegex(ValueError,"S5_ACTUAL_SUPPLIER"):
            d.review(ROOT,p)
        p=prior();p["strict_pair_evaluated"]=True
        with self.assertRaisesRegex(ValueError,"S5_ACTUAL_SUPPLIER"):
            d.review(ROOT,p)
        p=prior();p["2027_2030_demonstrated_demand_minus_supply_MTU"]["2027"]=0
        with self.assertRaisesRegex(ValueError,"ANNUAL_ELIGIBLE_SUPPLY"):
            d.review(ROOT,p)

    def test_corrupt_catalog_and_historical_fabricated_qualification_fail_closed(self):
        qa,_=d.checked_source(ROOT,d.QA_REL)
        qa["target_coverage"].pop()
        with self.assertRaisesRegex(ValueError,"FROZEN_TARGET_SET_NOT_22"):
            d.validate_qa(qa)
        qa,_=d.checked_source(ROOT,d.QA_REL)
        qa["registered_official"]["metrics"]["independent_pairs"]=1
        with self.assertRaisesRegex(ValueError,"HISTORICAL_ORIGINAL"):
            d.validate_qa(qa)

    def test_real_repository_handoff_fresh_sqlite_requery_and_no_production_claim(self):
        s,cases,files=d.review(ROOT,prior())
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"handoff"
            report,hand=d.write_result(p,s,cases,files)
            check=d.fresh_readback(p)
            self.assertEqual(check["cases"],22)
            self.assertEqual(check["HOLD"],22)
            self.assertEqual(hand["S6_full_database_integration"],"NOT_RUN")
            self.assertFalse(hand["promotion_allowed"])
            self.assertFalse(hand["production_DB_write_allowed"])
            self.assertEqual(hand["eligible_to_integrate_verified_pairs"],0)
            with self.assertRaisesRegex(ValueError,"OUTPUT_EXISTS"):
                d.write_result(p,s,cases,files)
            (p/"s6-research-handoff.json").write_text(json.dumps({
                **hand,"eligible_to_integrate_verified_pairs":7}))
            with self.assertRaisesRegex(ValueError,"S6_HANDOFF_MISMATCH"):
                d.fresh_readback(p)

if __name__=="__main__":
    unittest.main()
