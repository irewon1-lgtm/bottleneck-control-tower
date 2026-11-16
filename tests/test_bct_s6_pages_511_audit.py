"""Prove the published BCT 511 is historical research, not 511 verified pairs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s6_pages_511_audit as p

def fixture():
    categories=(["reviewed"]*23+["structured"]*211+["discovery"]*277)
    records=[{"id":f"{i:064x}","category":cat,
              "is_future_candidate":False}
             for i,cat in enumerate(categories)]
    ids={f"{i:064x}" for i in range(1703)}
    counts=Counter(categories)
    dashboard={
       "counts":{"evidence":511,"future_candidates":{"S1":0,"S2":0,"S3":0}},
       "records":records,
       "historical_data_at":"2026-10-14T23:16:13.592709+00:00",
       "data_at":"2026-11-16T00:49:38+00:00",
       "sector_rankings":{"count_kind":"SOURCE_LINKED_RESEARCH_RECORDS_NOT_VERIFIED_SHORTAGES",
                          "ranked_record_count":508,"unclassified_count":3,
                          "rows":[{"evidence_count":508}]},
       "sector_rankings_live":{"ranked_record_count":520,"new_original_verified":12,
                               "historical_source_rows":508,
                               "no_verified_supply_shortage_promoted":True,
                               "rows":[{"evidence_count":520}]},
       "source_backlog":{"historical_rank_input_count":511,
                         "rank_input_not_increased_by_rss":True,
                         "audit_matches_live_sidecar":False}
    }
    manifest={
       "generated_at":"2026-11-16T09:23:16.207227+00:00",
       "rss_article_count":10992,
       "evidence_count":1703,
       "evidence_bytes":123456,
       "site_type":"PUBLIC_STATIC_READ_ONLY",
       "new_ai_calls":0,
       "source_branch":"codex/bct-v4-integration",
       "code_commit":"ce1c28ce20ea0dbccaef14794a03e81f0061eec3",
       "historical_data_at":"2026-10-14T23:16:13.592709+00:00",
    }
    return (manifest,dashboard,Counter(p.CATEGORY_COUNT),ids,ids,
            manifest["evidence_bytes"])

class TestS6Historic511(unittest.TestCase):
    def test_exact_categories_and_live_overlay_not_proven_shortage(self):
        args=fixture()
        report=p.audit_counts(*args)
        self.assertEqual(report["historical_dashboard_record_count"],511)
        self.assertEqual(report["historical_evidence_breakdown"],
                         {"discovery":277,"reviewed":23,"structured":211})
        self.assertEqual(report["published_detailed_evidence_files"],1703)
        self.assertEqual(report["live_overlay_sector_ranked_rows"],520)
        self.assertEqual(report["live_overlay_new_publisher_verified_unpaired"],12)
        self.assertEqual(report["latest_rss_article_count_in_published_build"],10992)
        self.assertEqual(report["automatically_promoted_shortage_candidates"],0)

    def test_511_is_not_1703_or_10992_and_no_auto_promotion(self):
        m,d,c,ids,ref,b=fixture()
        d["counts"]["evidence"]=1703
        with self.assertRaisesRegex(ValueError,"HISTORICAL_511_RECORD"):
            p.audit_counts(m,d,c,ids,ref,b)
        m,d,c,ids,ref,b=fixture()
        d["records"][0]["is_future_candidate"]=True
        with self.assertRaisesRegex(ValueError,"FALSE_POSITIVE_MARKET_PROMOTION"):
            p.audit_counts(m,d,c,ids,ref,b)

    def test_detail_category_1186_cpu_not_market_rank(self):
        m,d,c,ids,ref,b=fixture()
        c["cpu_product"]+=1
        with self.assertRaisesRegex(ValueError,"PUBLISHED_DETAIL_CATEGORY"):
            p.audit_counts(m,d,c,ids,ref,b)
        m,d,c,ids,ref,b=fixture()
        m["evidence_count"]=511
        with self.assertRaisesRegex(ValueError,"PUBLISHED_DETAIL_FILE_INVENTORY"):
            p.audit_counts(m,d,c,ids,ref,b)

    def test_old_historical_at_time_not_current_RSS(self):
        m,d,c,ids,ref,b=fixture()
        d["source_backlog"]["rank_input_not_increased_by_rss"]=False
        with self.assertRaisesRegex(ValueError,"511_RANK_IS_HISTORICAL"):
            p.audit_counts(m,d,c,ids,ref,b)
        m,d,c,ids,ref,b=fixture()
        d["historical_data_at"]="2026-11-16T09:23:16+00:00"
        with self.assertRaisesRegex(ValueError,"HISTORICAL_RANK_GENERATION_DATE"):
            p.audit_counts(m,d,c,ids,ref,b)

    def test_sector_rows_508_historical_plus_12_verified_unpaired(self):
        m,d,c,ids,ref,b=fixture()
        d["sector_rankings_live"]["new_original_verified"]=22
        with self.assertRaisesRegex(ValueError,"NEW_ORIGINALS_ARE_NOT_MARKET_SHORTAGES"):
            p.audit_counts(m,d,c,ids,ref,b)
        m,d,c,ids,ref,b=fixture()
        d["sector_rankings"]["ranked_record_count"]=511
        with self.assertRaisesRegex(ValueError,"HISTORICAL_RANK_SOURCE_NOT_508"):
            p.audit_counts(m,d,c,ids,ref,b)

    def test_source_free_sqlite_new_process_requery_no_write(self):
        report=p.audit_counts(*fixture())
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"proof"
            p.write(out,report)
            self.assertEqual(p.requery(out)["historical_records"],511)
            with self.assertRaisesRegex(ValueError,"OUTPUT_EXISTS"):
                p.write(out,report)
            path=out/"published-511-reconciliation.json"
            record=json.loads(path.read_text())
            record["LIVE_writes"]=1
            path.write_text(p.canon(record))
            with self.assertRaisesRegex(ValueError,"PUBLISHED_PROOF_RECORD_CHANGED"):
                p.requery(out)

if __name__=="__main__":
    unittest.main()
