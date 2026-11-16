"""Adversarial tests for full S6 shard reconstruction, source units and URL dedup."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from bct.future_github import _shards,_raw,_sha,assemble
from bct.objective_lock import stamp_export
import bct_s6_full_sidecar_reconcile as q

def sample():
    h="a"*64
    candidate=stamp_export({
        "version":1,
        "results":{
          "a":{"id":"a","origin_url":"https://example.org/article/1",
               "origin_publisher":"A","provenance_verified":True,
               "publication_verified":True,"published_at":"2026-10-01",
               "body_sha256":h,"body_status":"FULL",
               "evidence":{"DEMAND":["something"],"SUPPLY":["something else"]},
               "candidate":True},
          "b":{"id":"b","origin_url":"https://example.org/article/1",
               "body_sha256":h,"body_status":"PARTIAL",
               "evidence":{"DEMAND":["another"]}},
          "c":{"id":"c","origin_url":"https://different.org/news",
               "body_sha256":"b"*64,"body_status":"UNAVAILABLE",
               "evidence":{}}},
        "hypotheses":{"h":{"current":{"evidence":[{"document_id":"a"},
                                                 {"document_id":"unrelated"}]}}},
        "events":{"one":{"documents":["b","nonexistent"]}}
    })
    tracking={"version":1,"targets":[
      {"id":"target-"+str(i),"target":"test-"+str(i),
       "history":[{"status":"OBSERVE","sources":
        (["https://example.org/article/1"] if i in (0,1) else [])}]}
        for i in range(22)]}
    verified={"items":[]}
    m1={"reconstructed_sha256":"c"*64,"generation_shards":2,
        "manifest_result_count":3,"manifest_hypothesis_count":1}
    m2={"reconstructed_sha256":"d"*64,"generation_shards":1,
        "manifest_targets_count":22}
    r1={"full_document_sha256":"c"*64,"fetched_shards":2}
    r2={"full_document_sha256":"d"*64,"fetched_shards":1}
    heads={q.SIDE_BRANCH:"e"*40,q.DATA_BRANCH:"f"*40}
    return candidate,tracking,verified,heads,(m1,m2),(r1,r2)

class TestS6AllActualShardUnits(unittest.TestCase):
    def test_project_native_assembler_rechecks_entire_document_and_shard_hash(self):
        doc={"results":{"a":{"evidence":{"DEMAND":["x"]}}},
             "hypotheses":{"h":{"current":{"stage":"OBSERVE"}}},
             "version":1}
        fields,chunks=_shards(doc)
        assert len(chunks)==1
        raw,count=chunks[0]
        m={"fields":fields,
           "document_sha256":_sha(_raw(doc)),
           "item_counts":{"results":1,"hypotheses":1,"version":1},
           "shards":[{"sha256":_sha(raw),"item_count":count}],
           "total_item_count":3}
        self.assertEqual(assemble(m,lambda part:raw),doc)
        with self.assertRaisesRegex(ValueError,"shard hash"):
            assemble(m,lambda part:raw+b"tampered")
        with self.assertRaisesRegex(ValueError,"reconstructed document"):
            assemble({**m,"document_sha256":"0"*64},lambda part:raw)

    def test_full_sidecar_article_evidence_tags_are_not_independent_pairs(self):
        c,t,v,h,m,r=sample()
        z=q.audit(c,t,v,h,m,r)
        ev=z["stored_records"]
        self.assertEqual(ev["stored_result_document_ids"],3)
        self.assertEqual(ev["records_with_role_tagged_evidence_not_qualified_pairs"],2)
        self.assertEqual(ev["records_with_both_demand_and_supply_tags_not_independent"],1)
        self.assertEqual(ev["provenance_plus_publication_flagged_originals_not_full_audit"],1)
        self.assertEqual(ev["unique_result_original_urls"],2)
        self.assertEqual(ev["result_url_repeat_excess_records"],1)
        self.assertEqual(ev["distinct_stored_body_hashes"],2)
        self.assertEqual(ev["hypothesis_and_event_document_references_checked"],4)
        self.assertEqual(ev["missing_referenced_result_ids"],2)
        self.assertEqual(z["qualified_independent_supply_demand_pairs"],
                         "NOT_PROVEN_BY_SHARD_LINKS")
        self.assertEqual(z["S6_full_operating_research_DB_integration"],"NOT_RUN")

    def test_per_target_links_are_not_distinct_originals_across_targets(self):
        c,t,v,h,m,r=sample()
        z=q.audit(c,t,v,h,m,r)
        stats=z["target_source_links"]
        self.assertEqual(stats["registered_target_ids"],22)
        self.assertEqual(stats["unique_target_link_url_pairs"],2)
        self.assertEqual(stats["unique_source_urls_across_all_targets"],1)
        self.assertEqual(stats["cross_target_repeated_url_pair_excess"],1)
        self.assertFalse(z["published_511_reproduced"])

    def test_legacy_fixed_sources_not_double_counted_in_target(self):
        target={"id":"t","history":[{"sources":["https://host.com/a",
                         "https://host.com/a"],"comparison_inputs":{"demand":{
                         "evidence":[{"url":"https://host.com/b"}]}}}]}
        baseline={"sources":[{"url":"https://host.com/a"},
                             {"url":"https://host.com/c"}]}
        links=q.one_target_links(target,baseline)
        self.assertEqual(len(links),3)

    def test_bad_result_id_prevents_false_source_identity(self):
        c,t,v,h,m,r=sample()
        c["results"]["a"]["id"]="other"
        with self.assertRaisesRegex(ValueError,"RESULT_RECORD_SOURCE_ID_COLLISION"):
            q.audit(c,t,v,h,m,r)

    def test_wrong_manifest_count_or_snapshot_digest_rejected(self):
        c,t,v,h,m,r=sample()
        bad=({**m[0],"manifest_result_count":10},m[1])
        with self.assertRaisesRegex(ValueError,"FULL_RESTORED_COUNTS_INCONSISTENT"):
            q.audit(c,t,v,h,bad,r)
        bad=({**m[0],"reconstructed_sha256":"0"*64},m[1])
        with self.assertRaisesRegex(ValueError,"PROOF_RESTORED_GENERATION_MISMATCH"):
            q.audit(c,t,v,h,bad,r)

    def test_source_free_report_sqlite_requery_and_tamper(self):
        c,t,v,h,m,r=sample()
        report=q.audit(c,t,v,h,m,r)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"audit"
            q.save(dest,report)
            self.assertEqual(q.fresh_readback(dest)["results"],3)
            with self.assertRaisesRegex(ValueError,"NO_OVERWRITE"):
                q.save(dest,report)
            payload=json.loads((dest/"s6-full-shard-sourcefree.json").read_text())
            payload["LIVE_writes"]=12
            (dest/"s6-full-shard-sourcefree.json").write_text(q.canonical(payload))
            with self.assertRaisesRegex(ValueError,"CORRUPT_SOURCE_FREE_PROOF"):
                q.fresh_readback(dest)

    def test_source_url_normalization_and_unsafe_protocol(self):
        self.assertEqual(q.public_url("HTTPS://Example.Com/A"),
                         "https://example.com/A")
        self.assertIsNone(q.public_url("file:///etc/passwd"))
        self.assertIsNone(q.public_url("javascript:alert(1)"))
        self.assertIsNone(q.public_url("missing://"))

if __name__=="__main__":
    unittest.main()
