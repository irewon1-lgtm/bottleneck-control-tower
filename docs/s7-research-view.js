"use strict";
// Pure S7 source-truth presentation and data contract. No candidate ranking logic.
((root) => {
  const hex = (v, size) => typeof v === "string" && new RegExp("^[a-f0-9]{" + size + "}$").test(v);
  const int = v => Number.isSafeInteger(v) && v >= 0;
  function validate(status) {
    if (!status || status.format !== "bct-s7-source-truth-preview-v1" ||
        status.status !== "PASS_RESEARCH_SOURCEBOUND_PRESENTATION_PREVIEW_ONLY" ||
        status.view !== "S7_PROOF_NOT_PUBLIC_OPERATING_PAGES") {
      throw new Error("Unverified S7 research dashboard source");
    }
    const r = status.research || {}, h = status.historical || {},
      d = status.deployment || {}, a = status.admission || {}, g = status.generations || {};
    if (h.status !== "FROZEN_2026_10_14_NOT_FRESH_EVIDENCE" ||
        h.data_at_utc !== "2026-10-14T23:16:13.592709+00:00" ||
        !int(h.record_count) || h.record_count !== 511 ||
        !h.counts || h.counts.reviewed !== 23 ||
        h.counts.structured !== 211 || h.counts.discovery !== 277 ||
        h.counts.reviewed + h.counts.structured + h.counts.discovery !== h.record_count ||
        h.sector_ranked_records !== 508 || h.unclassified_records !== 3 ||
        h.published_detail_files_different_units !== 1703 ||
        h.overlay_new_originals_unpaired !== 12 ||
        h.rank_is_current_verifiable_shortage !== false) {
      throw new Error("511 is not a freshly verified shortage count");
    }
    if (r.status !== "VERIFIED_S6_ISOLATED_SOURCE_FREE_HOLD" ||
        r.branch !== "research/bct-s6-sourcefree-ledger-20261116" ||
        !hex(r.commit_sha, 40) || !hex(r.sqlite_sha256, 64) ||
        r.rss_only_article_ids !== 316 || r.article_reentry_attempts !== 60 ||
        !r.body_states || r.body_states.FULL !== 24 ||
        r.body_states.PARTIAL !== 22 || r.body_states.UNAVAILABLE !== 14 ||
        r.body_states.FULL + r.body_states.PARTIAL + r.body_states.UNAVAILABLE !== r.article_reentry_attempts ||
        r.strict_original_publisher_body_date_verified !== 18 ||
        r.registered_target_holds !== 22 ||
        r.official_public_fact_codes_research_only !== 20 ||
        r.new_sourcebound_research_hints_not_independent_pairs !== 147 ||
        r.not_attempted_in_316_snapshot !== 256 ||
        r.admitted_qualified_independent_pairs !== 0 ||
        r.research_fact_units_not_additive_to_historical_count !== true ||
        r.stage6_status !== "PARTIAL") {
      throw new Error("Research count units or HOLD classification changed");
    }
    if (a.eligible_independent_pair_count !== 0 ||
        a.strict_pair_evaluation_for_all_corpus !== "NOT_PERFORMED" ||
        a.historical_rank_511_not_updated !== true ||
        a.new_research_hints_not_ranked !== true ||
        d.public_pages_deployed_by_this_job !== false ||
        d.operating_rss_or_sidecar_writes !== 0 || d.LIVE_writes !== 0 ||
        d.public_rank_writes !== 0 ||
        d.session7 !== "SOURCE_TRUTH_PREVIEW_NOT_PUBLIC_DEPLOYMENT" ||
        d.session8 !== "NOT_RUN") {
      throw new Error("Unverified ranking/deployment promotion");
    }
    if (!hex(g.main_code_commit, 40) || !hex(g.rss_data_commit_observed, 40) ||
        !hex(g.sidecar_commit_observed, 40) ||
        g.research_ledger_commit !== r.commit_sha ||
        !Number.isFinite(Date.parse(status.checked_at_utc)) ||
        Date.parse(status.checked_at_utc) < Date.parse(h.data_at_utc)) {
      throw new Error("Generation or source evidence clock invalid");
    }
    return status;
  }
  const summary = d => ({
    historicalCount: d.historical.record_count,
    historicalDate: d.historical.data_at_utc,
    oldReviewed: d.historical.counts.reviewed,
    oldStructured: d.historical.counts.structured,
    oldDiscovery: d.historical.counts.discovery,
    attempted: d.research.article_reentry_attempts,
    strictOriginals: d.research.strict_original_publisher_body_date_verified,
    hints: d.research.new_sourcebound_research_hints_not_independent_pairs,
    sourceFacts: d.research.official_public_fact_codes_research_only,
    targetHolds: d.research.registered_target_holds,
    strictPairs: d.admission.eligible_independent_pair_count,
    renderedAt: d.checked_at_utc,
    stage6: d.research.stage6_status
  });
  const api = {validate, summary};
  root.BCTResearch = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
