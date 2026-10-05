# READY_TO_ACTIVATE — approval required, not activated

This branch prepares REVIEW_LEAD SHADOW only. No merge, production Action dispatch, repository-variable write, LIVE write or review-state remote branch creation was performed. No source/semantic/Objective Lock/EARLY criteria changed. Original acquisition workflow has no change, avoiding shared timeout/success-status effects. The exact 83aaf61 review_intake.py, review_leads.py and deterministic precursor_v2.py hashes remain intact.

## Actual audited path

RSS live environment check is scheduled at 22:00 and 10:00 UTC (07:00/19:00 KST) and supports workflow_dispatch. RSS stores metadata in radar_items; new-document-manifest includes collection_started_at, prior IDs/URLs and new document_id/url/collected_at. RSS AI is separately scheduled at 22:20/10:20 UTC; future-bottleneck at 22:45/10:45 UTC. No schedules were changed.

New precursor evidence acquisition starts on completion of successful main RSS workflow. `new_precursor_cycle.py` calls the existing capture/verify/store path, then discovery/freeze and data/LIVE persistence. Original `acquire` conditions, permissions, concurrency, timeout, steps and failure behavior are preserved byte-for-byte in full. Nothing was inserted into its source/DB/V2/EARLY logic.

Prepared connection:

1. The separate workflow reads the **existing** `precursor-private-cache` artifact from the completed acquisition run, with no producer step added or changed. It uses the actual `workflow_run.created_at` as the capture-window start, scans only private-cache capture metadata, and reuses the existing proof loader for new PASS bodies (RSS seeds and opposite-side acquisitions). Older cached bodies are not loaded. No re-fetch or corpus scan. A missing artifact fails only SHADOW input preparation: no prior REVIEW record is changed or rolled back. This may happen if upstream evaluation failed before its existing artifact upload; it is an acknowledged input-availability limit, not a reason to alter that job's behavior. The cache artifact is already uploaded before data/LIVE persistence, so later upstream persistence failures do not inherently prevent independent review.
2. Separate `REVIEW_LEAD SHADOW intake` workflow starts on acquisition completion, without requiring its conclusion to be success. Same-repository main non-PR only, feature flag required. No upstream job depends on it.
3. Restore only `refs/heads/review-lead-shadow-state`, rejecting foreign paths, symlinks/submodules. Process handoff with frozen intake in `var/review-state/review-lead-shadow/store`. No DB/LIVE/V2/early root is restored or passed.
4. Store immutable activation, intake receipts, first/history, pending semantic queue, semantic provenance, review-time sidecars and run audits. Persist only own namespace with CAS, immutable prior-file checks and non-forced push. Persistence and audit upload are attempted even if SHADOW processing failed, preserving partial evidence without rolling back earlier review records.
5. Derived summary emits only new REVIEW_LEAD or meaningful REVIEW_LEAD updates/explicit refutation/confirmation. HOLD/EXCLUDED stay in audit/queue, not per-document notifications. No Slack/email/UI/API added. New-origin observations keep independence UNKNOWN unless source-bound review verifies it; never an EARLY claim.

## Time and semantic contract

Actual first SHADOW start seals an activation epoch and the unchanged intake activation; neither is derived from source publication. Only acquired_at on/after this cutover is eligible for prospective delivery, and the existing intake additionally checks timezone-aware published_at <= acquired_at <= recorded_at. Earlier documents are audited as BACKFILL and omitted from the normal prospective intake. Bootstrap therefore does not relabel already-acquired documents as prospective; first subsequent acquisitions are eligible. Explicit local backfill testing stays BACKFILL.

published_at, acquired_at, available_at are unchanged source values. Pending queue preserves intake_started_at/intake_recorded_at with first_review_recorded_at UNKNOWN until a card exists. Later semantic completion keeps the original queue and writes a new receipt/semantic provenance; review-times preserves earliest intake start and actual first-card recorded time separately. EARLY first-met and T/T_scope stay UNKNOWN; no date inference/backdate/lead-time substitution.

Machine extraction is the frozen deterministic event/identifier/locator code, not semantic proof. Queue includes document ID/hash, events, candidate scope suggestions explicitly unverified, reason, raw source document and method PENDING_AI_OR_MANUAL. No semantic reader is automatically installed or called. An attributed existing-schema packet is required to complete review; annotation_method, annotator, annotated_at, automatic_extraction and semantic_review_method are retained separately. Semantic-free intake remains HOLD/PENDING, not EXCLUDED. Explicit source-bound EVIDENCE/REVIEW/CONFIRMATION/REFUTATION append uses the existing state rules, never auto-EARLY.

## Minimum activation changes AFTER explicit approval

1. Reflect this prepared branch into main, including the existing frozen REVIEW dependencies from 83aaf61 (main currently lacks review_intake/review_leads/precursor_v2 and optional hook). Preserve their hashes and the unchanged contract; no need to change any engine or DB. The branch differs from current main only by pre-existing shadow/review additions/research artifacts and this prepared connection, not changes to existing EARLY/Objective logic.
2. Set the GitHub repository variable `BCT_REVIEW_SHADOW_ENABLED` to the exact string `true`. Without it, the entire new workflow is skipped. The producer workflow is unchanged regardless of this flag. No cloud allowlist/secret/service setting is required.
3. Let the next normal RSS/acquisition completion bootstrap the dedicated review state. State is permanently preserved in `review-lead-shadow-state`, with the existing 30-day source cache and new 30-day audit artifact supplementary. Existing contents:write/actions:read GITHUB_TOKEN permissions are used. No manual production dispatch or broad queue run is needed.

Disable by clearing/setting the flag false, leaving all existing review records intact. No destructive cleanup or reset.

## Tests actually executed

Eight requested safety checks: PASS each, with synthetic source fixtures and real existing capture/proof/storage functions. New-source storage hashes unchanged; forced review failure does not alter completed source storage; duplicate first/alert suppressed; same scope/hypothesis appends; no semantic input queues HOLD without alert; confirmation never EARLY/review success; old acquire time never prospective; operational roots/ancestors/symlinks and traversal rejected.

Additional local bare-Git test verifies dedicated branch CAS, append-only prior hashes and no main/LIVE refs. Workflow structure test verifies the full original job/workflow bytes unchanged, no new dependency/schedule/conclusion constraint, and a separate flag-gated artifact consumer. YAML and every modified workflow shell block passed parse/bash -n checks.

175 relevant boundary/V2/EARLY/prospective/collector tests PASS. 62 additional forecast/quick-review regressions PASS; 1 existing test SKIP because independent frozen real pre-public holdout/archived precursor facts are unavailable. Total 237 PASS, 1 SKIP; skip is not a performance PASS. No historical ablation rerun or real operating Action was executed. Real GitHub workflow delivery, GITHUB_TOKEN branch policy and next prospective intake remain to be verified after approved activation; these are not claimed tested here.

## Reproduction (no production activation)

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_review_shadow.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python review-leads/shadow-20261005/validate.py

Offline shadow bootstrap/run uses only an explicitly selected saved-body bundle:

    PYTHONPATH=src .venv/bin/python -m bct.review_shadow initialize --state <isolated-parent>/review-lead-shadow
    PYTHONPATH=src .venv/bin/python -m bct.review_shadow run --input <handoff/input.json> --state <isolated-parent>/review-lead-shadow

To complete a pending queue, supply `--semantic <Objective-bound-packets.json>`; queued original bodies are reused by exact document ID/hash. Explicit followup: `append --input <bound-source-bundle.json> --state <isolated-parent>/review-lead-shadow --review-id <review-ID> --event <attributed-bound-event.json>`. It requires a literal validated review ID and the existing source/state validators. This is not automatic stage-2 investigation.
