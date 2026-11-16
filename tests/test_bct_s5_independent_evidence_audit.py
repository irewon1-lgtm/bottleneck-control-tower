"""Session 5 negative and positive integrity tests; no original or private token."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import bct_s5_independent_evidence_audit as s5

WINDOWS=[15,13,34,27,18,13,14,17,25,18,46]
EVENTS=[3,0,1,1,0,3,1,0,0,0,1]

def fixtures():
    sources=[];receipts=[]
    for i,(windows,events) in enumerate(zip(WINDOWS,EVENTS)):
        reason="TARGET_FIELDS_UNKNOWN" if events else "CPU_ENTITY_ONLY_SEMANTICS_PENDING"
        item={
            "document_id":f"doc-{i:02}",
            "body_sha256":f"{i+1:064x}",
            "raw_sha256":f"{i+101:064x}",
            "total":windows,"success":windows,"failed":0,"unread":0,
            "read_state":"READ_COMPLETE","review_state":"READ_EVIDENCE_HOLD",
            "meaning_analysis_failed":False,
            "source_validation":"EXACT_NATIVE_AND_BODY_HASHES",
            "target_review_performed":True,
            "reason_code":reason,
            "source_bound_event_count":events,
            "graph_independent_pair_count":0,
            "strict_independent_pair_count":0,
            "strict_forecast_candidate_count":0,
            "LIVE_writes":0}
        sources.append(item)
        receipts.append({
            **{key:item[key] for key in s5.COMPARED},
            **{key:(0 if key=="strict_pair_count" else item[key]) for key in s5.COUNTS},
            "event_traces":[{"event_id":f"event-{i}-{n}",
                             "document_id":item["document_id"]} for n in range(events)],
            "pair_traces":[],
            "missing_fields":["customer_group","specification"] if events else []})
    s4={
        "format":s5.S4_FORMAT,
        "status":"PASS_SOURCE_BOUND_CPU_READBACK",
        "counts":{"total":240,"success":240,"failed":0,"unread":0},
        "exact_original_sources":11,
        "new_epoch_private_ack":s5.S4_ACK,
        "new_epoch_sqlite_sha256":s5.S4_SQLITE,
        "eight_table_remote_restore":True,
        "old_archive_ref_untouched":True,
        "previous_private_state_ref_untouched":True,
        "private_ref_writes":0,
        "automatic_qualified_supply_demand_adoption":False,
        "new_model_calls":0,
        "forecast_accuracy":"UNVERIFIED",
        "source_versions":sources,
        "semantic_review":{
            "exact_source_semantic_reviews":11,
            "original_exact_body_validation":11,
            "semantic_review_failures":0,
            "automatic_LIVE_promotions":0,
            "source_bound_events":10,
            "graph_independent_pair_count":0,
            "strict_independent_pair_count":0,
            "strict_forecast_candidate_count":0}}
    return s4,receipts

class Session5EvidenceGateTest(unittest.TestCase):
    def test_actual_cohort_shape_holds_and_no_false_promotion(self):
        s4,receipts=fixtures()
        report,cases=s5.triage(s4,receipts)
        self.assertEqual(report["source_bound_events"],10)
        self.assertEqual(report["blocker_counts"],{
            "CPU_ENTITY_ONLY_SEMANTICS_PENDING":5,"TARGET_FIELDS_UNKNOWN":6})
        self.assertEqual(report["missing_target_field_counts"],{
            "customer_group":6,"specification":6})
        self.assertEqual(report["independently_original_verified_supply_demand_pairs"],0)
        self.assertEqual(report["automatically_promoted_candidates"],0)
        self.assertEqual(report["session5_goal"],
                         "PARTIAL_NO_INDEPENDENT_QUALIFIED_DEMAND_SUPPLY_PAIRS")
        self.assertEqual(len(cases),11)
        self.assertNotIn("document_id",json.dumps(cases))
        self.assertNotIn("source_quote",json.dumps(cases))

    def test_reject_fake_original_success_or_private_sha_change(self):
        s4,receipts=fixtures()
        s4["new_epoch_sqlite_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"S4_IMMUTABLE"):s5.triage(s4,receipts)
        s4,receipts=fixtures()
        s4["counts"]["unread"]=1
        with self.assertRaisesRegex(ValueError,"S4_IMMUTABLE"):s5.triage(s4,receipts)

    def test_reject_missing_or_duplicate_semantic_case(self):
        s4,receipts=fixtures()
        with self.assertRaisesRegex(ValueError,"MISSING_OR_EXTRA"):
            s5.triage(s4,receipts[1:])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_SEMANTIC"):
            s5.triage(s4,receipts+[deepcopy(receipts[0])])

    def test_reject_same_doc_changed_body_version_and_event_identity(self):
        s4,receipts=fixtures()
        receipts[0]["raw_sha256"]="e"*64
        with self.assertRaisesRegex(ValueError,"MISSING_OR_EXTRA"):
            s5.triage(s4,receipts)
        s4,receipts=fixtures()
        receipts[0]["event_traces"][0]["document_id"]="different-doc"
        with self.assertRaisesRegex(ValueError,"PRIVATE_GRAPH_EVENT"):
            s5.triage(s4,receipts)

    def test_reject_missing_target_without_field_blocker(self):
        s4,receipts=fixtures()
        receipts[0]["missing_fields"]=[]
        with self.assertRaisesRegex(ValueError,"CAUSE_INCONSISTENT"):
            s5.triage(s4,receipts)

    def test_reject_unknown_field_or_unverified_analysis(self):
        s4,receipts=fixtures()
        receipts[0]["missing_fields"]=["the_secret_snippet"]
        with self.assertRaisesRegex(ValueError,"PRIVATE_SEMANTIC_GRAPH"):
            s5.triage(s4,receipts)
        s4,receipts=fixtures()
        receipts[0]["source_validation"]="NOT_VERIFIED"
        with self.assertRaisesRegex(ValueError,"PRIVATE_SEMANTIC_SOURCE"):
            s5.triage(s4,receipts)

    def test_even_positive_counter_is_not_a_verified_primary_pair(self):
        s4,receipts=fixtures()
        s4["source_versions"][0]["graph_independent_pair_count"]=1
        s4["source_versions"][0]["strict_independent_pair_count"]=1
        s4["semantic_review"]["graph_independent_pair_count"]=1
        s4["semantic_review"]["strict_independent_pair_count"]=1
        receipts[0]["graph_independent_pair_count"]=1
        receipts[0]["strict_pair_count"]=1
        receipts[0]["pair_traces"]=[{}]
        report,cases=s5.triage(s4,receipts)
        self.assertEqual(report["session5_goal"],
                         "BLOCKED_POSITIVE_PAIR_REQUIRES_TWO_VERIFIED_PRIMARY_ORIGINALS")
        self.assertEqual(sum(x["actual_eligible_pairs_for_auto_promotion"] for x in cases),0)

    def test_fresh_process_sqlite_roundtrip_and_tamper_detection(self):
        s4,receipts=fixtures()
        report,cases=s5.triage(s4,receipts)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"s5"
            saved=s5.write_receipt(out,report,cases)
            self.assertEqual(s5.readback(out)["sources"],11)
            self.assertTrue(saved["cases_sqlite_sha256"])
            with self.assertRaisesRegex(ValueError,"OUTPUT_DIRECTORY_ALREADY_EXISTS"):
                s5.write_receipt(out,report,cases)
            (out/"s5-summary.json").write_text(json.dumps({**saved,"cases_count":10}))
            with self.assertRaisesRegex(ValueError,"REQUERY_CASE_COUNT"):
                s5.readback(out)

if __name__=="__main__":
    unittest.main()
