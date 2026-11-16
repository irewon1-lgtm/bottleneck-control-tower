"""S6 read-only operating branch manifest and S5 HOLD handoff regression cases."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s6_operating_manifest_baseline as s6
from bct.objective_lock import stamp_export

HEADS={"data":"a"*40,"future-bottleneck-data":"b"*40}
HOLD="UNKNOWN"

def parent():
    return stamp_export({
       "format":"bct-s5-22-target-closed-disposition-v1",
       "cohort_disposition":"PASS_ALL_22_TARGETS_EXPLICITLY_CATEGORIZED",
       "targets_total":22,"targets_reviewed":22,
       "qualified":0,"rejected":0,"hold":22,
       "LIVE_candidates_created":0,"production_research_DB_writes":0,
       "production_rank_writes":0,
       "full_10k_article_research_audit":"NOT_PERFORMED",
       "sqlite_sha256":"a"*64,"cases_sha256":"b"*64,
    })

def handoff(p):
    return stamp_export({
      "format":"bct-s6-research-intake-pending-v1",
      "S5_scoped_22_target_review":"PASS",
      "eligible_to_integrate_verified_pairs":0,"hold_cases_for_research_DB":22,
      "promotion_allowed":False,"production_DB_write_allowed":False,
      "S6_full_database_integration":"NOT_RUN",
      "parent_sha256":s6.sha256(s6.canon(p)),
      "source_sqlite_sha256":p["sqlite_sha256"],
      "source_cases_sha256":p["cases_sha256"]
    })

def wrapper(path,obj):
    b=s6.canon(obj).encode("utf-8")
    blob=hashlib.sha1(b"blob "+str(len(b)).encode()+b"\x00"+b).hexdigest()
    return {"path":path,"encoding":"base64","sha":blob,
            "content":base64.b64encode(b).decode("ascii")}

def dataset():
    source_objs={
      "precursor_index":{
        "format":"bct-new-precursor-collection-v1",
        "independent_pair_count":0,"early_frozen":0,
        "new_verified_documents":0,"unverified_source_holds":1,
        "completed_at":"2026-11-16T01:36:21+00:00"
      },
      "v4_acquisition":stamp_export({
         "format":"bct-public-acquisition-1",
         "counts":{"new_verified_documents":0}
      }),
      "v4_research":stamp_export({
         "format":"bct-public-research-1",
         "analysis":{"states":{"PARTIAL":35,"READ_EVIDENCE_HOLD":21,"UNREAD":165},
                     "trace_total":221,"trace_truncated":True},
         "generation":{"producer_run_id":123},
         "clocks":{"persisted_at":"2026-11-16T00:50:12+00:00"}
      }),
      "future_candidates_manifest":{
         "format":"bct-sharded-sidecar-v1",
         "document_sha256":"c"*64,
         "shards":[{"path":"a.part.json","sha256":"d"*64,"item_count":7}],
         "item_counts":{"results":10,"hypotheses":4,"events":20},
         "total_item_count":34,
      },
      "future_tracking_manifest":{
        "format":"bct-sharded-sidecar-v1",
        "document_sha256":"e"*64,
        "shards":[{"path":"b.part.json","sha256":"f"*64,"item_count":22}],
        "item_counts":{"targets":22,"runs":4},
        "total_item_count":26,
      }
    }
    sources={k:wrapper(path,source_objs[k]) for k,(branch,path) in s6.SOURCES.items()}
    return sources,dict(HEADS),parent(),handoff(parent())

class S6MetadataGate(unittest.TestCase):
    def test_five_immutable_manifests_cohort_with_no_evidence_inflation(self):
        sources,heads,p,h=dataset()
        report,records=s6.audit(sources,heads,p,h)
        self.assertEqual(report["manifest_target_records"],22)
        self.assertEqual(report["candidate_shard_manifest_counts"]["results"],10)
        self.assertTrue(report["candidate_result_items_are_not_qualified_evidence"])
        self.assertEqual(report["published_sector_evidence_511"],"NOT_DETERMINABLE_FROM_MANIFESTS")
        self.assertEqual(report["S6_full_operating_DB_integration"],"NOT_RUN")
        self.assertEqual(report["S5_held_targets"],22)
        self.assertEqual(len(records),5)
        self.assertFalse(report["legacy_precursor_index_objective_stamped"])
        self.assertEqual(report["operating_data_branch_writes"],0)

    def test_false_511_and_late_evidence_not_claimed_even_with_many_result_ids(self):
        sources,heads,p,h=dataset()
        manifest=json.loads(base64.b64decode(sources["future_candidates_manifest"]["content"]))
        manifest["item_counts"]["results"]=99999
        manifest["total_item_count"]=100023
        sources["future_candidates_manifest"]=wrapper("future-candidates.json",manifest)
        report,_=s6.audit(sources,heads,p,h)
        self.assertEqual(report["published_sector_evidence_511"],"NOT_DETERMINABLE_FROM_MANIFESTS")
        self.assertEqual(report["actual_qualified_independent_pairs"],"NOT_EVALUATED_S6_OPERATING_SHARDS")

    def test_git_blob_or_path_tamper_fails_closed(self):
        s,heads,p,h=dataset()
        s["precursor_index"]["sha"]="f"*40
        with self.assertRaisesRegex(ValueError,"GITHUB_SOURCE_BLOB_HASH_MISMATCH"):
            s6.audit(s,heads,p,h)
        s,heads,p,h=dataset()
        s["precursor_index"]["path"]="future-candidates.json"
        with self.assertRaisesRegex(ValueError,"PUBLIC_GITHUB_FILE_WRAPPER_BAD"):
            s6.audit(s,heads,p,h)

    def test_source_missing_wrong_branch_or_target_mismatch(self):
        s,heads,p,h=dataset();del s["future_tracking_manifest"]
        with self.assertRaisesRegex(ValueError,"MISSING_OPERATING_METADATA_SOURCE"):
            s6.audit(s,heads,p,h)
        s,heads,p,h=dataset();heads["data"]="unsafe"
        with self.assertRaisesRegex(ValueError,"BAD_OPERATING_BRANCH_REF"):
            s6.audit(s,heads,p,h)
        s,heads,p,h=dataset()
        track=json.loads(base64.b64decode(s["future_tracking_manifest"]["content"]))
        track["item_counts"]["targets"]=21
        track["total_item_count"]=25
        s["future_tracking_manifest"]=wrapper("future-tracking.json",track)
        with self.assertRaisesRegex(ValueError,"CANONICAL_TARGET_COUNT_MISMATCH"):
            s6.audit(s,heads,p,h)

    def test_parent_must_remain_all_22_hold_and_no_live_promotion(self):
        s,heads,p,h=dataset();p["qualified"]=1
        with self.assertRaisesRegex(ValueError,"PARENT_S5_SOURCE_PROOF_INVALID"):
            s6.audit(s,heads,p,h)
        s,heads,p,h=dataset();h["promotion_allowed"]=True
        with self.assertRaisesRegex(ValueError,"S5_S6_HANDOFF_BINDING_CHANGED"):
            s6.audit(s,heads,p,h)
        s,heads,p,h=dataset();p["hold"]=21
        with self.assertRaisesRegex(ValueError,"PARENT_S5_SOURCE_PROOF_INVALID"):
            s6.audit(s,heads,p,h)

    def test_research_trace_truncation_cannot_be_claimed_complete(self):
        s,heads,p,h=dataset()
        value=json.loads(base64.b64decode(s["v4_research"]["content"]))
        value["analysis"]["trace_truncated"]=False
        s["v4_research"]=wrapper("v4-public/research.json",value)
        with self.assertRaisesRegex(ValueError,"PUBLIC_TRACE_CANNOT_BE_ASSUMED_COMPLETE"):
            s6.audit(s,heads,p,h)

    def test_fresh_sqlite_and_corrupt_handoff_fails(self):
        s,heads,p,h=dataset()
        report,rows=s6.audit(s,heads,p,h)
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"new"
            saved=s6.persist(out,report,rows)
            self.assertEqual(s6.fresh_readback(out)["files"],5)
            with self.assertRaisesRegex(ValueError,"NO_OVERWRITE"):
                s6.persist(out,report,rows)
            (out/"s6-index-baseline.json").write_text(s6.canon({
                **saved,"published_sector_evidence_511":511})+"\n")
            with self.assertRaisesRegex(ValueError,"INCOMPLETE_OR_FALSE_EVIDENCE_COUNT"):
                s6.fresh_readback(out)

if __name__=="__main__":
    unittest.main()
