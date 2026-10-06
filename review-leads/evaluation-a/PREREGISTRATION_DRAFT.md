# BCT A-stage preregistration — DRAFT, not approved

Version: BCT_EVALUATION_A_DRAFT_1. This document is authoritative; config.json is a checked companion. Its full-file SHA-256 is in manifest.json, never inside itself. This is A-stage preparation, not a complete statistical protocol. No approval, t0, formal epoch, MARKET implementation, main merge or observer activation is supplied here.

## A. Agreed purpose and protections

Find concrete targets worth human/ChatGPT stage-2 research from demand/supply precursors before public bottleneck reporting. Default interest horizon is 12–36 months, not an entry gate. REVIEW_LEAD is research intake, not confirmed bottleneck, EARLY success, market-wide scarcity or investment advice. Demand competition, supply rigidity and substitution constraints are later evidence fields, not a new ALL-PASS REVIEW gate.

Preserve Objective Lock version/hash/export rules, REVIEW contract, existing semantic criteria, V2/EARLY/LIVE, first/history, frozen diagnostic outputs, schedules and flags. No new AI, source expansion, mass backfill, canary, ablation, MARKET promotion, double reading, recall/placebo or statistical evaluation in A. Prior work is exploratory/evaluation-excluded. Existing operation stays on, including backlog preservation; review capacity never stops collection.

## B. Technical preparation and rationale

Use a read-only GitHub metadata observer, not an acquisition-completion hook: it can see missed runs when upstream never finishes. Prepare a workflow template outside .github/workflows; it cannot activate on this branch or main. Read only API run/jobs/artifact metadata, dedicated SHADOW Git blobs and existing data index. Never execute artifact code, restore operational stores as writable workspaces or evaluate document candidates. Artifact existence, successful download, successful restore and successful provenance are separate claims.

Report per-workflow total_count, query completeness, query interval and unique run IDs. Latest-job detail is not full job history. Same run observed twice does not add documents twice. A cumulative state snapshot and latest-run increment are different; unavailable increments stay UNKNOWN. Missing runs, capture failure, permission denial, artifact failure, pending semantics and completed reading without leads are distinct. No semantic input means pending/HOLD, never EXCLUDED. State branch absence means no persisted records, not proof there were no upstream documents or human research.

Expected RSS schedule comes from current main (10:00,22:00 UTC); acquisition follows successful main RSS; SHADOW follows eligible acquisition completion. No own production schedule is invented. Actual created_at/run_started_at/job started_at remain separate from nominal cron. Unknown skip causes remain UNKNOWN: skipped job cannot be assumed to write its own diagnosis.

Reserve refs/heads/review-lead-evaluation-state exclusively for a future approved evaluation writer, separate from data, live-state and review-lead-shadow-state. validate_state_ref permits only this exact evaluation ref. No operational state writer or evaluation branch creation is implemented/activated in A. Current reports and test artifacts live only on this A work branch. Future writer would require its own serialization/CAS and immutable records before approval, not just a different folder on a shared state branch. Observer template uses contents:read/actions:read and publishes audit artifacts only; it cannot persist Git state. High-privilege workflow_run/PR artifact execution is forbidden. GitHub-hosted monitoring shares GitHub's outage domain and is not an independent external monitor.

### t0 and cohorts

t0 = actual server-side event time proving the user-approved preregistration version reached main. A future activation must link approval record, approved document SHA-256, main SHA and event ID/time. Git author/committer times, source publication and intake times cannot substitute. If server time is unavailable t0 stays UNKNOWN. A config has t0=null and epoch=null; draft validation rejects activation. No t0+7/14 dates exist now.

BACKFILL/PROSPECTIVE_REVIEW (document delivery mode) and EXPLORATORY_EXCLUDED/SHAKEDOWN/EVALUATION (evaluation cohort) are orthogonal. Approved t0 may be linked by a new append-only cohort sidecar, never overwriting cards, activation or mode. SHAKEDOWN ending does not start formal evaluation: incomplete prerequisites keep material in research queue. New rules/periods require separate approval and next epoch. B cannot start automatically.

### First hypothesis and subsequent evidence

Prepare separate source-bound sidecars: target/scope, observed change and quote/locator/body hash, claim, assumptions, raw prediction period or UNKNOWN, refutation conditions, annotator/method and actual reading/recording timestamps, input documents and hypothesis hash. Reuse review_leads.documents/reference/validate_fields for body/version/locator verification; do not reassess EARLY or rewrite frozen events. A claim is not a confirmed fact.

H0 is first recorded hypothesis, not retroactively reconstructed certainty. Changed scope/claim/prediction period means new H1, new actual timestamp and explicit previous-hypothesis hash/reference. Adding evidence to unchanged claims is an EVIDENCE append, not a backdated H1. Unavailable historical reading times are UNKNOWN. Helper anchors the exact immutable first card time and hash, never caller-supplied replacements. Old records need not be migrated.

review_lead_first_at = actual immutable first REVIEW_LEAD card storage time after semantic reading; HOLD/confirmation does not supply it. market_candidate_first_at = actual first recording that the same hypothesis version meets a separately approved future MARKET subset; currently UNIMPLEMENTED/UNKNOWN. Intake time is processing latency only. Plan to compare these separate clocks with T_scope later, not compute lead time in A.

### Exposure and T_scope

First semantic reading exposure record includes input document IDs/hashes (keep their dates), start/completion, reader/model/method, web-search use and actual cited URLs/access times if searched, independently available model knowledge information or UNKNOWN. A model's own asserted cutoff/independence is not proof. Separate first input from later confirmation sources. Sidecars never create semantic reading or fill missing times.

T_scope is a confirmed actual bottleneck public time for a fixed target scope within a stated source-search scope. No matching scope, firstness or reliable date => UNKNOWN. Not finding confirmation in supplied documents is not evidence it never existed publicly. T at/before first card is not leading success. Later discovery of earlier T adds an evaluation/confirmation record, never changes first card. No new corporate/T search or automatic engine status change in A.

## C. User decisions (unapproved proposals)

| Decision | Proposal and rationale | Approval state |
|---|---|---|
| SHAKEDOWN checkpoints/end | t0+7 days interim, t0+14 days initial end review; inspect actual arrivals/readings before B | Proposal only; duration not approved |
| Human time / monetary cost | Set weekly available reviewer minutes and total cost ceiling before activation; A supplies no assumed budget | UNDECIDED |
| Alert tolerance / throughput cap | Determine from observed schedule latency and queue service rate; approve tolerances and research-start limit, preserve all pending material | UNDECIDED; no operational alarms/caps |
| Formal-evaluation readiness | Verified delivery/state recovery and reading provenance, approved budget, frozen B protocol/reference sample and independent assessment prerequisites | Proposed checklist; separate approval required |

No decision in this document is implied authorized by approval to prepare A. Existing agreed purpose/protections need not be reopened.

## D. B-stage decisions, not implemented

Before formal evaluation separately fix sampling rate, comparisons, double reading, recall audit, placebo, denominator/uncertainty conventions, statistical go/no-go and adequate sample sizes. Decide after measured arrivals and completed readings; retain document/event/pair/lead denominators separately. Existing corpus is development/diagnostic material, not an independent holdout. No EARLY quota or compulsory first lead. Zero outcomes are valid; incomplete data is not PASS. Market subset rules, performance metrics and independent observer failure-domain mitigations remain outside A. Completion of this draft is not a completed evaluation protocol.

## Reproduction and reading status

`PYTHONPATH=src python tools/review_evaluation_a.py --output review-leads/evaluation-a/current-observation.json`

Observer writes a new report only, never reuses or overwrites an existing output. Optional --prior-report supplies prior observer time; absence stays UNKNOWN. observation JSON contains raw safe metadata and measured values with provenance/interval/unit; CURRENT_STATUS.md interprets it. Synthetic helper tests are functional boundaries, not accuracy/lead-time evidence. Runtime production has deterministic extraction plus pending queue. AI/manual semantic completion requires attributed Objective-bound packets through existing review_shadow --semantic CLI; no automatic reader is installed or scheduled. This preparation does not alter that path.
