"""Session 7 source-truth dashboard gates. No synthetic public shortage admissions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import bct_s7_source_truth_preview as s7
from bct.objective_lock import stamp_export

HEAD={"research_sha":"0c15e7a0f94c1cfbcb4f6362bbbc5b5360106f65",
      "main_sha":"95206b4e235e60c2d46a677da5cce725aefe3f56",
      "sidecar_sha":"5a9452362ee1c4b97fefc66da25c7cbdcb6176fb",
      "data_sha":"a42a370044c3a5f8dc67af1faa1ec8bac6993e48"}

def receipts(folder):
    research=Path(folder)/"research"
    historical=Path(folder)/"historical"
    research.mkdir();historical.mkdir()
    r=stamp_export({
      "format":"bct-s6-durable-sourcefree-research-ledger-v1",
      "sqlite_sha256":s7.KNOWN_RESEARCH_DB_SHA,
      "source_counts":{"article_intake":316,"source_reentry_plan":60,
          "source_attempts":60,"target_holds":22,"research_facts":20,
          "source_bound_hints":147},
      "source_attempt_states":{"FULL":24,"PARTIAL":22,"UNAVAILABLE":14},
      "source_original_verified":18,
      "registered_targets_preserved_hold":22,
      "strict_eligible_independent_pairs_admitted":0,
      "previous_public_rank_511":"HISTORICAL_NOT_UPDATED",
      "data_or_future_branch_writes":0,"LIVE_writes":0,"public_Pages_deploys":0
    })
    h=stamp_export({
      "format":"bct-s6-pages-511-rootcause-v1",
      "source_run_id":43838794301,
      "source_artifact_id":s7.ORIGINAL_PAGES_ARTIFACT_ID,
      "source_artifact_digest":s7.ORIGINAL_PAGES_ARTIFACT_DIGEST,
      "historical_rank_input_last_updated_at":s7.HISTORICAL_DATE,
      "historical_dashboard_record_count":511,
      "historical_evidence_breakdown":{"reviewed":23,"structured":211,"discovery":277},
      "historical_ranked_sector_rows":508,
      "historical_unclassified_records":3,
      "published_detailed_evidence_files":1703,
      "latest_rss_article_count_in_published_build":10992,
      "live_overlay_new_publisher_verified_unpaired":12,
      "historical_rank_input_not_increased_by_RSS":True,
      "automatically_promoted_shortage_candidates":0,
      "sqlite_sha256":"f"*64
    })
    (research/"research-summary.json").write_text(s7.canon(r))
    (historical/"published-511-reconciliation.json").write_text(s7.canon(h))
    return research,historical

def requery_mock():
    return patch.multiple(s7,
       durable_readback=lambda x:{"status":"PASS_DURABLE_S6_RESEARCH_SQLITE_FRESH_READBACK",
           "articles":316,"source_attempts":60,"verified_public_originals":18,
           "source_bound_hints":147,"research_fact_codes":20,
           "HOLD_targets":22,"qualified_pairs":0},
       historical_readback=lambda x:{"status":"PASS_PUBLIC_511_SQLITE_FRESH_REQUERY",
           "historical_records":511,"detail_files":1703,"live_overlay":520})

class SourceTruthTest(unittest.TestCase):
    def test_two_independent_sources_do_not_add_511_and_147(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=receipts(t)
            with requery_mock():
                report=s7.compile_status(a,b,**HEAD,now="2026-11-16T13:00:00Z")
            self.assertEqual(report["historical"]["record_count"],511)
            self.assertEqual(report["research"]["new_sourcebound_research_hints_not_independent_pairs"],147)
            self.assertEqual(report["admission"]["eligible_independent_pair_count"],0)
            self.assertEqual(report["research"]["registered_target_holds"],22)
            self.assertEqual(report["deployment"]["session8"],"NOT_RUN")
            self.assertFalse(report["deployment"]["public_pages_deployed_by_this_job"])
            output=Path(t)/"s7-research-status.json"
            check=s7.save_status(report,output)
            self.assertEqual(check["historical_511"],511)
            self.assertEqual(check["originals_strict"],18)
            self.assertEqual(check["sha256"],s7.sha(output.read_bytes()))
            with self.assertRaisesRegex(ValueError,"OUTPUT_OVERWRITE"):
                s7.save_status(report,output)

    def test_reject_historical_511_promoted_to_new_validated_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=receipts(t)
            p=b/"published-511-reconciliation.json"
            for key,value in [("historical_dashboard_record_count",658),
                              ("automatically_promoted_shortage_candidates",1),
                              ("historical_rank_input_last_updated_at","2026-11-16T12:59:00Z")]:
                original=json.loads(p.read_text())
                original[key]=value
                p.write_text(s7.canon(original))
                with requery_mock(), self.assertRaisesRegex(ValueError,"HISTORICAL_PUBLISHED_SITE"):
                    s7.compile_status(a,b,**HEAD)
                p.write_text(s7.canon(receipts_original(b)))

    def test_reject_qualified_market_pair_spoofing_from_147_hints(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=receipts(t)
            p=a/"research-summary.json"
            value=json.loads(p.read_text())
            value["strict_eligible_independent_pairs_admitted"]=147
            p.write_text(s7.canon(value))
            with requery_mock(), self.assertRaisesRegex(ValueError,"RESEARCH_PROVENANCE"):
                s7.compile_status(a,b,**HEAD)

    def test_reject_unpinned_sha_and_mismatched_source_clock(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=receipts(t)
            with requery_mock():
                with self.assertRaisesRegex(ValueError,"UNPINNED_GITHUB"):
                    s7.compile_status(a,b,**{**HEAD,"research_sha":"latest"})
                with self.assertRaisesRegex(ValueError,"NAIVE_TIME"):
                    s7.compile_status(a,b,**HEAD,now="2026-11-16T13:00:00")
                report=s7.compile_status(a,b,**HEAD)
            report["admission"]["eligible_independent_pair_count"]=1
            with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_STAGING"):
                s7.save_status(report,Path(t)/"invalid.json")

def receipts_original(path):
    """Recover expected unmodified synthetic proof for successive tamper cases."""
    with tempfile.TemporaryDirectory() as temp:
        r,h=receipts(temp)
        return json.loads((h/"published-511-reconciliation.json").read_text())

if __name__=="__main__":
    unittest.main()
