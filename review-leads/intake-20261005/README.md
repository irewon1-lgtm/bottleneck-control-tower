# Separate REVIEW_LEAD semi-automatic intake

Purpose: repeatable stage-1 human research triage, not EARLY, strict or forecasting performance. Existing contract BCT_REVIEW_LEAD_CONTRACT_1 and rule BCT_REVIEW_LEAD_RULES_1 are unchanged. Intake adapter version BCT_REVIEW_INTAKE_1 has its own implementation/extractor binding and actual activation timestamp in a separate store. No score, extra collector or paid service.

## Actual audit

- RSS metadata enters `bct.collectors.rss.collector`, then radar_items DB; RSS does not fetch article bodies. `rss-live-check.yml` emits a new-document manifest and snapshot-only artifact. `.github/scripts/live_document_snapshot.py` preserves snapshot bodies, not independently proven full article metadata.
- `precursor_collection.capture` fetches/validates canonical/body/metadata, persists raw HTML, captures and body-hash document records. `target_acquisition.verify` provides provenance fields, actual acquired_at, raw/body hashes and version. `precursor_collection.cycle` also invokes existing discovery/freeze; REVIEW intake does not call this cycle or change it.
- `precursor_v2.extract` supplies source-bound events, fields, quotation/context locators. Its keywords/flags are suggestions, not a truth-labeling semantic reader. No extractor/pair/S3/EARLY code changed.
- Existing quick/manual review (`future_review`, `future_manual_review`) is operational candidate tracking/export/import with reference locks; no automatic REVIEW_LEAD producer exists there. Its original format is not spoofed. The already defined REVIEW_LEAD annotation shape is reused.
- `review_leads.assess/make_card/activate/write_first/append_event/load_store` validate literal references, scopes and UNKNOWN, seal immutable first/history with Objective Lock, and leave EARLY counts zero. Existing make_card mode calculation is not sufficient for same-day prospective delivery: new adapter records actual acquisition cutover independently for NEW records only, with missing metadata kept UNKNOWN. Original first cards untouched.
- Existing `precursor-acquisition.yml` runs after RSS and uses 30-day cache and LIVE store. No workflow, main, LIVE root, schedule or public app is changed. This branch adds an **unactivated optional post-save hook**, tested independently.

## Minimal connection

New saved full source delta → provenance/raw/body verification → unchanged deterministic extractor → attributed semantic packet (AI or human) → existing review assessor → separate REVIEW_LEAD/HOLD/EXCLUDED/CONFIRMATION first/history.

The optional `.github/scripts/review_lead_intake.py` accepts either an Objective-bound full-document bundle or `BCT_REVIEW_CACHE` plus the existing new RSS manifest. In cache mode only listed capture IDs/URLs are opened, completed/baseline IDs are excluded, original HTML/body/metadata proofs are checked; unavailable or invalid captures get separate EXCLUDED reasons. Nothing is fetched. No entire corpus scan. Max100 is a safety limit; no automatic batch loop. Review errors are explicitly BLOCKED in a separate output and do not fail collection or V2.

No semantic packet means HOLD with full machine event suggestions, `semantic_review=PENDING`. It does **not** mean machine confirmation or automatically invented hypothesis. A packet binds document_id/body hash and contains the existing complete source-bound annotation, annotator/method/time, facts vs hypothesis, assumptions, specific questions, refutation, unknowns and confirmation review. Existing assay and source references are validated, not AI accuracy claimed. Completing a pending review adds an immutable receipt; changed completed annotation requires explicit append review, no overwrite. For new qualified records the first card stores manual_or_ai_semantic_review=true. No TARGET-name branches/dictionaries.

Exact origin/body or identical body versions are duplicate deliveries; verified same literal scope fields + same hypothesis_key reuse first and append evidence/review. Different literal model/facility scopes never merge; unknown attributes cannot serve as identity evidence. Alias-equivalence and paraphrased hypotheses are not automatically merged. Requotes retain source metadata and are not treated as independent proof. Hypothesis keys must describe the same mechanism across evidence packets, not include document IDs.

## Offline commands

Prepared Objective-bound full body delta with optional semantic packets:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m bct.review_intake \
      --input <new-body-delta.json> --contract review-leads/contract.json \
      --semantic <bound-semantic-packets.json> --store <separate-review-store> \
      --output <review-report-prefix> --prospective

Omit --semantic to preserve unreviewed HOLD intake. Packet format examples: regression-semantic.json and sample-semantic.json. These contain manual/AI annotations, **not** case-name rules in code. A new store seals adapter hashes. Existing diagnostic stores bound to earlier code are immutable receipts; do not reinitialize/overwrite their activation to use updated adapter code.

Optional post-save hook (not configured or executed by operational Actions):

    BCT_REVIEW_NEW_DOCUMENTS=<new-rss-manifest.json> BCT_REVIEW_CACHE=<existing-precursor-cache> \
      BCT_REVIEW_STORE=<separate-review-store> BCT_REVIEW_OUTPUT=<review-report-prefix> \
      BCT_REVIEW_PROSPECTIVE=1 PYTHONPATH=src .venv/bin/python .github/scripts/review_lead_intake.py

Use BCT_REVIEW_SEMANTIC for an attributed bound packet file, if available. No new API or automatic LLM service is installed. AI/human semantic reading is still needed for promotion; unreviewed or ambiguous entries wait.

## Recorded tests and fixed small trial

Regression reuses the four previously preserved manual readings; same generic assessor gives Katy REVIEW_LEAD, Hemerdon REVIEW_LEAD, PrSM HOLD, eActros EXCLUDED. This validates processing/references/state preservation, **not autonomous semantic accuracy**. The final regression receipt is in final-regression-result.json.

Five recent, not previously REVIEW_LEAD-read documents were selected by stored timestamp descending, excluding four original examples. IDs, body/input/code hashes and selection were sealed at commit 0b34d7e before the sample output. Full bodies read by the assistant, semantic packets added separately, one sample execution: 0 REVIEW_LEAD / 2 HOLD / 3 EXCLUDED / 0 CONFIRMATION. They are preserved historical inputs, BACKFILL, not newly collected LIVE documents. Existing provenance PASS flags are retained; no new online original fetch/verification is claimed. The Loadstar visible date vs stored metadata difference is not corrected. Reuters quotations are not counted as independent Defense News origins.

The sample used executed-code/review_intake.py (hash exactly equals sample-manifest.json). Subsequent **synthetic-test-only** hardening fixes alternate-document-ID duplicate delivery, pending followup recovery, same-scope reuse, missing-publication handling and adds fuller rendering. No source extraction, sample input, semantic labels or sample outcome were tuned or rerun. Code diff is preserved in Git. Final adapter stores intentionally have a new implementation binding; prior stores stay unchanged. No claim that the fixed five were re-executed with later code.

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest -q \
      tests/test_review_intake.py tests/test_review_leads.py \
      tests/test_precursor_v2.py tests/test_shadow_site_loader_v2.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python review-leads/intake-20261005/validate.py

These are boundary/regression tests; no A/B ablation or EARLY execution. No full Python/JS suite or operating workflow execution is claimed. Duplicate, unknown, binding, mismatch, confirmation, source cutover, append-only replay, failure isolation and new-ID-only cache reading are synthetic tests, distinct from actual development samples.

## Limits

This is a working semi-automatic path, not an autonomous semantic analyst. Missing extractor events/fields, rhetoric, synonym resolution, confirmation scope and actual source equivalence still need attributed semantic reading. HOLD is safe until then. No accuracy/precision/recall estimate or prospective lead-time success is supported by these development samples. Operational activation requires a separate authorized change; it was not performed here.
