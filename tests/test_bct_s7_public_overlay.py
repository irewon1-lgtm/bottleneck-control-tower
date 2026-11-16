"""S7 Pages safe-overlay adverse tests: 511 preserved, no false 147 rank."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s7_public_overlay as o
from bct.objective_lock import stamp_export

MAIN="3682798909066413ab174798275268c51a8bbfa4"

def status():
    sha="0c15e7a0f94c1cfbcb4f6362bbbc5b5360106f65"
    return stamp_export({
        "format":o.FORMAT,
        "status":"PASS_RESEARCH_SOURCEBOUND_PRESENTATION_PREVIEW_ONLY",
        "view":"S7_PROOF_NOT_PUBLIC_OPERATING_PAGES",
        "checked_at_utc":"2026-11-16T13:25:00+00:00",
        "historical":{
            "status":"FROZEN_2026_10_14_NOT_FRESH_EVIDENCE",
            "data_at_utc":o.HIST_DATE,"record_count":511,
            "counts":{"reviewed":23,"structured":211,"discovery":277},
            "sector_ranked_records":508,"unclassified_records":3,
            "published_detail_files_different_units":1703,
            "overlay_new_originals_unpaired":12,
            "rank_is_current_verifiable_shortage":False},
        "research":{
            "status":"VERIFIED_S6_ISOLATED_SOURCE_FREE_HOLD",
            "branch":o.RESEARCH_BRANCH,"commit_sha":sha,
            "sqlite_sha256":o.RESEARCH_SQL_SHA,
            "rss_only_article_ids":316,"article_reentry_attempts":60,
            "body_states":{"FULL":24,"PARTIAL":22,"UNAVAILABLE":14},
            "strict_original_publisher_body_date_verified":18,
            "registered_target_holds":22,
            "official_public_fact_codes_research_only":20,
            "new_sourcebound_research_hints_not_independent_pairs":147,
            "not_attempted_in_316_snapshot":256,
            "admitted_qualified_independent_pairs":0,
            "research_fact_units_not_additive_to_historical_count":True,
            "stage6_status":"PARTIAL"},
        "admission":{
            "eligible_independent_pair_count":0,
            "strict_pair_evaluation_for_all_corpus":"NOT_PERFORMED",
            "historical_rank_511_not_updated":True,
            "new_research_hints_not_ranked":True
        },
        "deployment":{
            "public_pages_deployed_by_this_job":False,
            "operating_rss_or_sidecar_writes":0,
            "LIVE_writes":0,"public_rank_writes":0,
            "session8":"NOT_RUN"},
        "generations":{
            "main_code_commit":MAIN,
            "rss_data_commit_observed":"a42a370044c3a5f8dc67af1faa1ec8bac6993e48",
            "sidecar_commit_observed":"5a9452362ee1c4b97fefc66da25c7cbdcb6176fb",
            "research_ledger_commit":sha
        }
    })

def fixture(base,settings=None):
    root=Path(base)/"site"
    (root/"api").mkdir(parents=True)
    root.joinpath("app.js").write_text("console.log('existing');")
    root.joinpath("index.html").write_text("""
<!doctype html><nav class="bct-tabs" aria-label="주요 화면">
        <a href="#candidates" data-nav="candidates">검토 중인 변화</a>
</nav><script src="./app.js" defer></script>""")
    dashboard={
        "counts":{"evidence":511,"future_candidates":{"S1":0,"S2":0,"S3":0}},
        "records":[{"id":format(i,"064x"),"category":"discovery"} for i in range(511)],
        "historical_data_at":o.HIST_DATE,
        "sector_rankings":{"ranked_record_count":508},
        "sector_rankings_live":{"new_original_verified":12,
                                "no_verified_supply_shortage_promoted":True},
        "publication":{"code_commit":"ce1c28ce20ea0dbccaef14794a03e81f0061eec3"}
    }
    if settings:dashboard.update(settings)
    raw=json.dumps(dashboard,ensure_ascii=False,separators=(",",":")).encode()
    (root/"api/dashboard.json").write_bytes(raw)
    manifest={"code_commit":dashboard["publication"]["code_commit"],
              "site_type":"PUBLIC_STATIC_READ_ONLY",
              "evidence_count":1703,
              "dashboard_sha256":o.hash_bytes(raw)}
    (root/"build-manifest.json").write_text(json.dumps(manifest))
    statuspath=Path(base)/"status.json"
    statuspath.write_text(json.dumps(status(),ensure_ascii=False))
    return root,statuspath

class S7SafePagesOverlay(unittest.TestCase):
    def test_isolated_report_preserves_511_and_original_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            site,st=fixture(temp)
            old={f:(site/f).read_bytes() for f in ("api/dashboard.json","app.js","build-manifest.json")}
            result=o.build(site,st,MAIN,43875515509)
            self.assertEqual(result["historical_511"],511)
            self.assertEqual(result["new_originals_verified"],18)
            self.assertEqual(result["independent_qualified_pairs_admitted"],0)
            self.assertEqual(result["source_status_sha256"],o.hash_bytes(st.read_bytes()))
            self.assertIn(o.TRUTH_ANCHOR,(site/"index.html").read_text())
            report=(site/"source-truth/index.html").read_text()
            self.assertIn("511건",report)
            self.assertIn("147개",report)
            self.assertIn("22개 등록 TARGET HOLD",report)
            self.assertNotIn("658건",report)
            self.assertIn("기존 병목 탐색판",report)
            for f,b in old.items():self.assertEqual((site/f).read_bytes(),b)
            with self.assertRaisesRegex(ValueError,"DUPLICATE_RESEARCH_OVERLAY"):
                o.build(site,st,MAIN,43875515509)

    def test_immutable_pages_manifest_drift_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            site,st=fixture(temp)
            raw=json.loads((site/"api/dashboard.json").read_text())
            raw["counts"]["evidence"]=658
            (site/"api/dashboard.json").write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,"EXISTING_PAGES_MANIFEST"):
                o.build(site,st,MAIN,43875515509)
            self.assertFalse((site/"source-truth").exists())

    def test_511_147_or_fabricated_strict_pair_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            site,st=fixture(temp)
            for mutator in [
                 lambda x:x["historical"].update(record_count=658),
                 lambda x:x["research"].update(new_sourcebound_research_hints_not_independent_pairs=165),
                 lambda x:x["admission"].update(eligible_independent_pair_count=1),
                 lambda x:x["research"].update(registered_target_holds=0),
                 lambda x:x["deployment"].update(LIVE_writes=1)
            ]:
                original=status()
                mutator(original)
                # Stamp the tampered test data to prove semantic check remains independent.
                st.write_text(json.dumps(stamp_export(original)))
                with self.assertRaisesRegex(ValueError,"HISTORICAL|RESEARCH_FACT|UNVERIFIED"):
                    o.build(site,st,MAIN,43875515509)
                self.assertFalse((site/"source-truth").exists())

    def test_wrong_generation_ref_or_future_time_cannot_replace_source(self):
        with tempfile.TemporaryDirectory() as temp:
            site,st=fixture(temp)
            with self.assertRaisesRegex(ValueError,"SOURCE_RUN_AND_DATA_GENERATION"):
                o.build(site,st,"a"*40,43875515509)
            src=status()
            src["checked_at_utc"]="2026-01-01T00:00:00Z"
            st.write_text(json.dumps(stamp_export(src)))
            with self.assertRaisesRegex(ValueError,"SOURCE_RUN_AND_DATA_GENERATION"):
                o.build(site,st,MAIN,43875515509)

    def test_old_html_link_shape_changed_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            site,st=fixture(temp)
            (site/"index.html").write_text("<html>replaced layout</html>")
            with self.assertRaisesRegex(ValueError,"EXISTING_SITE_HTML_NOT_APPROVED"):
                o.build(site,st,MAIN,43875515509)

if __name__=="__main__":
    unittest.main()
