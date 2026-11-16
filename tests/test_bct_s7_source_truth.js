"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const view = require("../docs/s7-research-view.js");

function valid() {
  const researchSha = "0c15e7a0f94c1cfbcb4f6362bbbc5b5360106f65";
  return {
    format: "bct-s7-source-truth-preview-v1",
    status: "PASS_RESEARCH_SOURCEBOUND_PRESENTATION_PREVIEW_ONLY",
    view: "S7_PROOF_NOT_PUBLIC_OPERATING_PAGES",
    checked_at_utc: "2026-11-16T13:00:00+00:00",
    historical: {
      status: "FROZEN_2026_10_14_NOT_FRESH_EVIDENCE",
      data_at_utc: "2026-10-14T23:16:13.592709+00:00",
      record_count: 511, counts: {reviewed:23, structured:211, discovery:277},
      sector_ranked_records:508, unclassified_records:3,
      published_detail_files_different_units:1703,
      overlay_new_originals_unpaired:12,
      rank_is_current_verifiable_shortage:false
    },
    research: {
      status:"VERIFIED_S6_ISOLATED_SOURCE_FREE_HOLD",
      branch:"research/bct-s6-sourcefree-ledger-20261116",
      commit_sha:researchSha, sqlite_sha256:"d0bef9da83910bf4ede638cea87df8f582bcb0cbb12033aee09aac64e832872d",
      rss_only_article_ids:316, article_reentry_attempts:60,
      body_states:{FULL:24,PARTIAL:22,UNAVAILABLE:14},
      strict_original_publisher_body_date_verified:18,
      registered_target_holds:22,
      official_public_fact_codes_research_only:20,
      new_sourcebound_research_hints_not_independent_pairs:147,
      not_attempted_in_316_snapshot:256,
      admitted_qualified_independent_pairs:0,
      research_fact_units_not_additive_to_historical_count:true,
      stage6_status:"PARTIAL"
    },
    generations: {
      main_code_commit:"95206b4e235e60c2d46a677da5cce725aefe3f56",
      rss_data_commit_observed:"a42a370044c3a5f8dc67af1faa1ec8bac6993e48",
      sidecar_commit_observed:"5a9452362ee1c4b97fefc66da25c7cbdcb6176fb",
      research_ledger_commit:researchSha
    },
    admission:{
      eligible_independent_pair_count:0,
      strict_pair_evaluation_for_all_corpus:"NOT_PERFORMED",
      historical_rank_511_not_updated:true,
      new_research_hints_not_ranked:true
    },
    deployment: {
      public_pages_deployed_by_this_job:false,
      operating_rss_or_sidecar_writes:0,LIVE_writes:0,public_rank_writes:0,
      session7:"SOURCE_TRUTH_PREVIEW_NOT_PUBLIC_DEPLOYMENT",
      session8:"NOT_RUN"
    }
  };
}
const clone = x => JSON.parse(JSON.stringify(x));

test("S7 source truth uses two distinct verified units, 511 history vs 18 originals vs 147 hints",()=>{
  const x=view.validate(valid());
  const vals=view.summary(x);
  assert.equal(vals.historicalCount,511);
  assert.equal(vals.oldReviewed+vals.oldStructured+vals.oldDiscovery,511);
  assert.equal(vals.strictOriginals,18);
  assert.equal(vals.hints,147);
  assert.equal(vals.strictPairs,0);
  assert.equal(vals.targetHolds,22);
  assert.equal(vals.stage6,"PARTIAL");
});

test("historical record changed without original proof must fail closed",()=>{
  for(const [field,value] of [["record_count",658],["rank_is_current_verifiable_shortage",true],
         ["data_at_utc","2026-11-16T14:00:00+00:00"]]){
    const x=valid();x.historical[field]=value;
    assert.throws(()=>view.validate(x),/511 is not/);
  }
  const x=valid();x.historical.counts.discovery=424;
  assert.throws(()=>view.validate(x),/511 is not/);
});

test("S7 cannot treat 147 new locator hints as strictly eligible pairs or auto-rank new results",()=>{
  const changes=[
   x=>{x.admission.eligible_independent_pair_count=147;},
   x=>{x.research.admitted_qualified_independent_pairs=18;},
   x=>{x.research.new_sourcebound_research_hints_not_independent_pairs=165;},
   x=>{x.admission.new_research_hints_not_ranked=false;},
   x=>{x.research.registered_target_holds=0;}
  ];
  for(const change of changes){
    const x=valid();change(x);
    assert.throws(()=>view.validate(x),/changed|promotion/);
  }
});

test("source reporting current must not imply unapproved Pages deployment or false freshness",()=>{
  const changes=[
   x=>{x.deployment.public_pages_deployed_by_this_job=true;},
   x=>{x.deployment.LIVE_writes=1;},
   x=>{x.deployment.session8="PASS";},
   x=>{x.generations.research_ledger_commit="f".repeat(40);},
   x=>{x.checked_at_utc="2026-01-01T00:00:00Z";}
  ];
  for(const change of changes){const x=valid();change(x);assert.throws(()=>view.validate(x));}
  assert.throws(()=>view.validate(null));
  assert.throws(()=>view.validate({}));
});

test("existing BCT UI includes route and local S7 source-only rendering dependency",()=>{
  const index=fs.readFileSync(path.resolve(__dirname,"../docs/index.html"),"utf8");
  const app=fs.readFileSync(path.resolve(__dirname,"../docs/app.js"),"utf8");
  assert.match(index,/data-page="research"/);
  assert.match(index,/s7-research-view\.js/);
  assert.match(app,/s7-research-status\.json/);
  assert.match(app,/window\.BCTResearch\.validate/);
  assert.match(app,/과거 511건 \+ 신규 연구 단서 147개를 더해 순위를 계산하지 않습니다/);
  assert.match(app,/loadS7SourceTruth/);
  assert.doesNotMatch(app,/researchStatus\s*=\s*511\s*\+\s*147/);
});
