"""BCT dual-ranking hostile regression tests; no network or operating writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s8_dual_ranking_overlay as rankings

MAIN="a"*40

def analyzed():
    return {"summary":{"checked_at":"2026-11-16T10:00:00+00:00"},
      "results":{
        "doc-a":{"id":"doc-a","title":"Demand contract","url":"https://one.example/order",
                 "body_status":"FULL","source":"Example One","checked_at":"2026-11-16T09:00:00+00:00"},
        "doc-b":{"id":"doc-b","title":"Supplier constraint","url":"https://two.example/capacity",
                 "body_status":"FULL","source":"Example Two","checked_at":"2026-11-16T09:00:00+00:00"},
        "doc-c":{"id":"doc-c","title":"Relief reported","url":"https://three.example/relief",
                 "body_status":"PARTIAL","source":"Example Three","checked_at":"2026-11-16T09:00:00+00:00"}
      },
      "hypotheses":{
        "hyp-a":{"current":{"scope":{"target":"Power transformer slots"},"evidence":[
            {"document_id":"doc-a","role":"DEMAND"},
            {"document_id":"doc-a","role":"DEMAND"},
            {"document_id":"doc-b","role":"SUPPLY"}]}},
        "hyp-b":{"current":{"scope":{"target":"power transformer slots"},"evidence":[
            {"document_id":"doc-b","role":"SUPPLY"},
            {"document_id":"doc-c","role":"RELIEF"}]}},
        "hyp-unknown":{"current":{"scope":{"target":"UNKNOWN"},"evidence":[
            {"document_id":"doc-a","role":"DEMAND"}]}}
      }}

def fixture(tmp):
    root=Path(tmp)/"site"
    (root/"api").mkdir(parents=True)
    (root/"source-truth").mkdir()
    root.joinpath("app.js").write_bytes(b"unchanged app")
    root.joinpath("index.html").write_text('<nav class="bct-tabs"><a href="#candidates" data-nav="candidates">검토 중인 변화</a>' +
         rankings.S7_ANCHOR + "</nav>",encoding="utf-8")
    dashboard={"counts":{"evidence":511},
        "historical_data_at":"2026-10-14T23:16:13.592709+00:00",
        "sector_rankings":{"ranked_record_count":508},
        "sector_rankings_live":{"rows":[{"name":"전력·발전","evidence_count":520,
                                           "rss_verified_count":12,"rank":1}],
                               "new_original_verified":12,
                               "no_verified_supply_shortage_promoted":True},
        "publication":{"code_commit":"b"*40}}
    raw=json.dumps(dashboard,ensure_ascii=False).encode()
    root.joinpath("api/dashboard.json").write_bytes(raw)
    root.joinpath("build-manifest.json").write_text(json.dumps({
       "site_type":"PUBLIC_STATIC_READ_ONLY","code_commit":"b"*40,
       "evidence_count":1703,"dashboard_sha256":hashlib.sha256(raw).hexdigest()}))
    root.joinpath("source-truth/status.json").write_text(json.dumps({
       "historical":{"record_count":511},
       "admission":{"eligible_independent_pair_count":0}}))
    return root

def proof(source):
    return {"sidecar_commit":"c"*40,"source_document_sha256":"d"*64,
       "sidecar_ui_sha256":"e"*64,
       "articles_with_screening_result":len(source["results"]),
       "hypothesis_slots":len(source["hypotheses"]),"sidecar_checked_at":"2026-11-16T10:00:00Z"}

class DualRankingTests(unittest.TestCase):
    def test_basic_signal_dedup_and_relief_penalty(self):
        source=analyzed()
        ranking,n=rankings.basic_ranking(source,observed_at=rankings.iso("2026-11-16T10:00:00Z"))
        self.assertEqual(n,2)
        self.assertEqual(len(ranking),1)
        row=ranking[0]
        self.assertEqual(row["article_count"],3)
        self.assertEqual(row["demand_articles"],1)
        self.assertEqual(row["supply_articles"],1)
        self.assertEqual(row["relief_articles"],1)
        self.assertEqual(row["source_hosts"],3)
        self.assertEqual(row["full_body_articles"],2)
        self.assertEqual(row["score_components"]["relief_penalty"],5)
        self.assertTrue(0<=row["score"]<=100)
        self.assertEqual(row["research_level"],"수요·공급 양쪽 단서")

    def test_only_one_side_is_never_high_confidence(self):
        source=analyzed()
        source["hypotheses"]["hyp-a"]["current"]["evidence"]=[
           {"document_id":"doc-a","role":"DEMAND"}]
        source["hypotheses"].pop("hyp-b")
        rows,_=rankings.basic_ranking(source,observed_at=rankings.iso("2026-11-16T10:00:00Z"))
        self.assertLessEqual(rows[0]["score"],49)
        self.assertEqual(rows[0]["research_level"],"한쪽 또는 부분 단서")

    def test_protected_research_unmodified_and_two_navigation_links(self):
        source=analyzed()
        with tempfile.TemporaryDirectory() as temp:
            root=fixture(temp)
            protected={name:(root/name).read_bytes() for name in
                 ("app.js","api/dashboard.json","build-manifest.json","source-truth/status.json")}
            result=rankings.build(root,source,proof(source),
                       {"rss_article_count":11064,"rss_data_commit":"f"*40},main_sha=MAIN)
            self.assertEqual(result["status"],"PASS_DUAL_RANKINGS_READONLY_OVERLAY")
            self.assertEqual(result["analysis_result_slots"],3)
            self.assertTrue(result["historical_511_preserved"])
            self.assertEqual(result["new_verified_pairs"],0)
            site=root.joinpath("index.html").read_text()
            self.assertIn(rankings.BASIC_ANCHOR,site)
            self.assertIn(rankings.EVIDENCE_ANCHOR,site)
            page=root.joinpath("rankings/index.html").read_text()
            self.assertIn("기본분석 선행신호 순위",page)
            self.assertIn("근거 검증 순위",page)
            self.assertIn("Power transformer slots",page)
            self.assertIn("전력·발전",page)
            report=json.loads(root.joinpath("rankings/report.json").read_text())
            self.assertEqual(report["legacy_dashboard_sha256"],
                             hashlib.sha256(protected["api/dashboard.json"]).hexdigest())
            self.assertEqual(report["evidence"]["source_verified_unpaired"],12)
            self.assertEqual(report["sidecar"]["articles_with_screening_result"],3)
            for name,old in protected.items():
                self.assertEqual((root/name).read_bytes(),old)
            with self.assertRaisesRegex(ValueError,"DUPLICATE_RANKING_OVERLAY"):
                rankings.build(root,source,proof(source),{},main_sha=MAIN)

    def test_fail_closed_on_forged_511_and_source_count(self):
        source=analyzed()
        with tempfile.TemporaryDirectory() as temp:
            root=fixture(temp)
            dashboard=json.loads((root/"api/dashboard.json").read_text())
            dashboard["counts"]["evidence"]=600
            (root/"api/dashboard.json").write_text(json.dumps(dashboard))
            with self.assertRaisesRegex(ValueError,"EXISTING_SITE_GENERATION"):
                rankings.build(root,source,proof(source),{},main_sha=MAIN)
            self.assertFalse((root/"rankings").exists())

    def test_cannot_promote_unverified_shortage_pair(self):
        source=analyzed()
        with tempfile.TemporaryDirectory() as temp:
            root=fixture(temp)
            path=root/"source-truth/status.json"
            path.write_text(json.dumps({"historical":{"record_count":511},
                             "admission":{"eligible_independent_pair_count":1}}))
            with self.assertRaisesRegex(ValueError,"S7_PROTECTED_EVIDENCE"):
                rankings.build(root,source,proof(source),{},main_sha=MAIN)
            self.assertFalse((root/"rankings").exists())

    def test_bad_evidence_total_rejected(self):
        source=analyzed()
        with tempfile.TemporaryDirectory() as temp:
            root=fixture(temp)
            path=root/"api/dashboard.json"
            d=json.loads(path.read_text())
            d["sector_rankings_live"]["rows"][0]["evidence_count"]=521
            raw=json.dumps(d).encode();path.write_bytes(raw)
            manifest=root/"build-manifest.json"
            m=json.loads(manifest.read_text())
            m["dashboard_sha256"]=hashlib.sha256(raw).hexdigest()
            manifest.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"EVIDENCE_AGGREGATE"):
                rankings.build(root,source,proof(source),{},main_sha=MAIN)

    def test_html_escaping_and_url_safety(self):
        evil="<script>alert(1)</script>"
        source=analyzed()
        source["hypotheses"]["hyp-a"]["current"]["scope"]["target"]=evil
        source["hypotheses"].pop("hyp-b")
        source["results"]["doc-a"]["url"]="javascript:alert(1)"
        rows,_=rankings.basic_ranking(source)
        self.assertEqual(rows[0]["example_urls"],["https://two.example/capacity"])
        page=rankings.html_page(rows,[{"rank":1,"sector":"Test","evidence_count":508,
            "historical_count":508,"source_verified_unpaired":0}],
            {"generated_at_utc":"2026-11-17T00:00:00Z",
             "sidecar":{"sidecar_commit":"c"*40,"articles_with_screening_result":3,
                        "hypothesis_slots":2,"sidecar_checked_at":None},
             "named_targets":1,"evidence":{"source_verified_unpaired":0}})
        self.assertNotIn(evil,page)
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn('href="javascript:',page)

    def test_unknown_hypotheses_do_not_create_rank(self):
        source=analyzed()
        source["hypotheses"]={"x":{"current":{"scope":{"target":"UNKNOWN"},
            "evidence":[{"document_id":"doc-a","role":"DEMAND"}]}}}
        rows,count=rankings.basic_ranking(source)
        self.assertEqual(rows,[])
        self.assertEqual(count,0)

if __name__=="__main__":
    unittest.main()
