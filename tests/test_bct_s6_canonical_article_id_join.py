"""S6 canonical vs sidecar article identity join: strict source-free negative tests."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from bct.objective_lock import stamp_export
import bct_s6_canonical_article_id_join as q

def prior():
    return stamp_export({
       "format":"bct-s6-exhaustive-sidecar-readonly-v1",
       "status":"PASS_EXACT_FULL_SHARD_RECONSTRUCTION_AND_SOURCE_LINK_COUNT",
       "operating_heads":{"data":q.PINNED_DATA,"future-bottleneck-data":q.PINNED_SIDE},
       "candidate_full_restore":{"fetched_shards":39,"full_document_sha256":"a"*64},
       "tracking_full_restore":{"fetched_shards":1},
       "stored_records":{"stored_result_document_ids":q.PINNED_RESULTS},
       "RSS_canonical_snapshot":{"radar_items":q.PINNED_RSS,
                                 "canonical_sqlite_sha256_expected":q.PINNED_CANONICAL_SHA},
       "sidecar_branch_writes":0,"LIVE_writes":0,
    })

def mini_data():
    c={"a":"active","b":"active","d":"inactive","e":"active"}
    r={"results":{"a":{"id":"a","body_status":"FULL"},
                  "b":{"id":"b","body_status":"PARTIAL"},
                  "c":{"id":"c","body_status":"UNAVAILABLE"}}}
    return c,r

class TestS6PinnedRealJoin(unittest.TestCase):
    def test_pinned_real_full_shard_report_guard(self):
        self.assertTrue(q.validate_prior(prior()))
        r=prior()
        r["stored_records"]["stored_result_document_ids"]=100000
        with self.assertRaisesRegex(ValueError,"PRIOR_FULL_40_SHARD"):
            q.validate_prior(r)
        r=prior();r["operating_heads"]["data"]="0"*40
        with self.assertRaisesRegex(ValueError,"PRIOR_FULL_40_SHARD"):
            q.validate_prior(r)

    def test_real_source_id_join_not_arithmetic_subtraction(self):
        c,r=mini_data()
        with patch.object(q,"PINNED_RSS",4), patch.object(q,"PINNED_RESULTS",3):
            prior_doc=prior()
            report,items=q.join_ids(c,r,"a"*64,prior_doc)
        self.assertEqual(report["id_join_counts"],{
            "BOTH":2,"CANONICAL_ONLY":2,"SIDECAR_ONLY":1})
        self.assertEqual(report["matched_article_body_states"],{
            "FULL":1,"PARTIAL":1})
        self.assertNotEqual(report["id_join_counts"]["CANONICAL_ONLY"],4-3)
        self.assertEqual(report["canonical_rss_ids"],4)
        self.assertEqual(report["sidecar_result_ids"],3)
        self.assertEqual(report["qualified_independent_supply_demand_pairs"],
                         "NOT_ESTABLISHED_BY_ID_JOIN")
        self.assertTrue(all(len(x["hashed_article_id"])==64 for x in items))
        self.assertFalse(any("title" in x or "url" in x for x in items))

    def test_no_duplicated_or_missing_canonical_articles(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"canonical.sqlite3"
            with sqlite3.connect(file) as con:
                con.execute("CREATE TABLE radar_items(id TEXT,status TEXT)")
                con.executemany("INSERT INTO radar_items VALUES (?,?)",
                                [("a","active"),("b","active"),("a","active"),("d","active")])
            with patch.object(q,"PINNED_RSS",4):
                with self.assertRaisesRegex(ValueError,"CANONICAL_RSS_ID_COUNT"):
                    q.rows_from_sqlite(file.read_bytes(),Path(d)/"copy.sqlite3")

    def test_source_free_sqlite_roundtrip_no_publication(self):
        c,r=mini_data()
        with patch.object(q,"PINNED_RSS",4),patch.object(q,"PINNED_RESULTS",3):
            report,rows=q.join_ids(c,r,"a"*64,prior())
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"join"
            q.persist(out,report,rows)
            self.assertEqual(q.readback(out),{
                "status":"PASS_PINNED_RSS_AND_SIDECAR_FRESH_SQLITE_ID_JOIN",
                "articles":4,"results":3,"matched":2,
                "missing_result":2,"sidecar_only":1})
            with self.assertRaisesRegex(ValueError,"OVERWRITE_EXISTING_LEDGER"):
                q.persist(out,report,rows)
            summary=out/"s6-article-id-join.json"
            value=json.loads(summary.read_text())
            value["LIVE_writes"]=1
            summary.write_text(q.canonical(value))
            with self.assertRaisesRegex(ValueError,"FALSE_OR_OUTDATED_ARTICLE_ID_JOIN"):
                q.readback(out)

    def test_wrong_result_generation_does_not_qualify_missing_set(self):
        c,r=mini_data()
        with patch.object(q,"PINNED_RSS",4),patch.object(q,"PINNED_RESULTS",7):
            with self.assertRaisesRegex(ValueError,"PINNED_RESULTS_DIFFERENT_GENERATION"):
                q.join_ids(c,r,"a"*64,prior())

if __name__=="__main__":
    unittest.main()
