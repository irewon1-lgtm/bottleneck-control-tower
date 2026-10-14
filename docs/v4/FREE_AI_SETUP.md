# GroqCloud only, Gemini disabled — V4 repair and frozen evaluation

Updated 2026-10-14 (Asia/Seoul). Read `EXECUTION_PLAN.md` and `PROGRESS.json` first. The fixed eight-stage goal and CPU GLiNER2 engine remain unchanged. Active AI: **GroqCloud Free Plan only**. Gemini code is retained, but routing/probes and key requirements are disabled. No third provider, paid fallback, upgrade or billing action.

## Current development quality trial (round3, 2026-10-14 UTC)

Existing key, Free account, model and account caps stay unchanged. New opt-in `context-reference-v1` sends exact bounded contexts identified by IDs; Python resolves only that ID then runs the original strict unique source and meaning checks. Literal values are not repaired. Legacy requests/cache scopes/quote rejection stay unchanged. New input policy `sentence-context-v3` prepares complete contexts up to1200characters/2windows; actual byte reservations still must fit6400 and the shared80% quota. This setting is for the frozen research trial, not operating adoption.

New20 actual sources (10 native-cache reuse/10 new source requests;FULL5/PARTIAL15) and71 inference/input files were frozen before predictions. Separate source-only AI author/reviewer/adjudicator reviewed40 windows and froze truth before target generation; this is not human verification. New CPU baseline18 valid/2 strict span failures, existing pinned installation reused. Selected scope14833/107299characters; actual8 received input windows7082characters. The remaining body, tables and attachments are not claimed analysed.

**9 new POSTs/8 responses,6149 input+703 output=6852 reported tokens, Free API cost0.** Failed400 usage is UNKNOWN and its5602 reservation is retained; platform usage/cost is separate and UNKNOWN. One `SCHEMA_GENERATION` HTTP400 stopped the contract;11 remain uncalled. No retry, auth GET, model/key/account change or alternative provider. Same contract had8 received outputs, so precise failure cause remains UNKNOWN.

Fixed event scorer on the common8: CPU TP2/FP22/FN3(P8.33%,R40%); Groq TP1/FP1/FN4(P50%,R20%). FN worsened. Moreover13 discovery-only gold targets have no event denominator: the scorer marks the source-supported A350F discovery as unmatched FP. Keep mechanical scores; they do not establish complete product-identification accuracy or verified fabrication. Old13 P/R0%/0% remains immutable and is a different corpus, not a paired before/after comparison. New source items2 accepted/1 rejected for a wrong transmitted context ID;5 empty replies. AI Shadow and operating automation HOLD. Known research S1/S2/S3 stays1/0/0, new0; lead performance NOT_RUN.

Evidence: `stage4-corpus/round3/outcome.json`, `scores.json`, `measurement-audit.json`, `http400-diagnosis.json`, `storage-preservation.json`. Trial/report tools are bounded and append-only; do not rerun to improve consumed scores. Future changes use development/authored cases and require another unused frozen evaluation. The shared API ledger preserves historical401/400 attempts, previous raw responses and the request-contract block.

## Authentication recovery and unchanged evaluation resume (2026-10-14 UTC)

Existing `GROQ_API_KEY`, Free account, proxy/CA and settings revision were preserved. The preceding read-only models GET at08:51:34 returned200. Its receipt is retained in `stage4-corpus/round2/auth-resume/auth-evidence.json`; readiness metadata still saysunknown, and the past401 cause is not established. Explicit one-shot recovery uses fresh evidence (at most1hour old), consumes authorization before HTTP, forbids attempted inputs and retains the original AUTH block until the unchanged router receives a real generation. No key/setting changes or additional authentication GETs occurred.

The fresh U740 input received a generation at09:00:47; its short quotations failed strict source validation. After inspecting that transport success, the remaining10 untouched eligible inputs ran with the exact frozen inference closure and existing quota spacing/caps. **11 new POSTs /11 responses /10,093 input +2,921 output =13,014 reported tokens /Free API cost0**. The former401 input was not retried; its earlier unknown usage/reservation remains. New evaluation results are additive artifacts: original responses, truth and scores remain unchanged.

Cumulative same-round evaluation:14 attempted/13 responses; contact4/context2 remain held. The13 response windows total5,717 characters (8.77% of all20 bodies); this is not whole-document accuracy. Returned10 items:8 rejected (4 AMBIGUOUS_QUOTE,4 VALUE_NOT_LITERAL),2 older source-valid advisories;6 empty responses are reported separately. Fixed product scoring on common13: CPU TP8/FP15/FN7 (P34.8%,R53.3%); Groq source-adopted TP0/FP2/FN15 (P0%,R0%). Raw model context/identity metrics and semantic roles are separate in the new report. Quantity-prefixed identities, nonliteral numeric values and order/supply confusion are preserved, not repaired. AI source-only gold is not human verification. Product FN increased: **adoption/AI Shadow HOLD**. Known development research S1/S2/S3 remains1/0/0; no evaluation item was promoted.

Evidence and offline report: `stage4-corpus/round2/auth-resume/scores.json`, `quote-diagnostics.json`, `storage-preservation.json`. Existing178 corpus artifacts,68 frozen contract hashes and99 prior SQLite events were preserved. New11 raw responses/jobs matched requery, and a restored owned-ledger copy matched every table in a fresh process. New auth guards17 +existing free-AI tests79 passed locally; final exact-commit CI is checked after push. CPU/model preparation, collection and prior whole local tests were not repeated. Operating main/DB/Actions/UI/alerts and AI schedules are unchanged.

Operator commands use the existing owned API ledger and shared rolling budget: `tools/v4_auth_resume.py --probe` requires unused fresh authorized evidence; `--continue` requires a received probe and skips every attempted input. These inputs are now exhausted: do not rerun either to seek better outputs. `tools/v4_auth_resume_report.py` writes once using unchanged scoring. Future inference fixes must use development cases and other unused evaluation documents. No cloud configuration change is needed for this recovered runtime.

The following sections retain earlier dated task results and blockers; use the latest PROGRESS authentication_resume for current state.

## Prior approved sequential research (2026-10-14)

Plan v1.8 continues from the actual remote `ef3321609210281757141d9b897e792333d9d5c7`. Original118/frozen50, consumed evaluation20, seven rejected items and stages1–3 remain unchanged. The new source20 and exact bounded input/model/prompt/scoring closure were frozen before predictions at `stage4-corpus/round2/freeze.json`. CPU weights/environment were reused; no install or model preparation was repeated. Read `round2/scores.json` and `round2/sequential-evidence.json` for current results; earlier sections below are dated history.

The changed development prompt retained the working wire schema and strict exact/unique quote binding. Four new POSTs produced three responses (one development, two evaluation), reporting **2,783 input + 1,293 output = 4,076 tokens**. The third evaluation request returned **HTTP401 `invalid_api_key`**, with unreported usage. The batch stopped with11 unattempted eligible documents and persisted WAIT_API/provider settings-change state. No retry, probe, new-key request, paid fallback or Gemini call followed. Historical HTTP400's cause remains UNKNOWN; its failed request was not repeated. Existing Free Plan limits/run caps/80% quotas remain enforced. Rolling budgets use reported actual tokens when present and retain conservative reservations when usage is unknown.

All20 official native/date proofs are retained;14 bounded inputs are eligible,4 contact-context blocked,2 context-held. Two blind source-only AI drafts plus a separate source-only adjudication reviewed14 windows' document scopes; this is not human verification. Same-input common2 product precision/recall: CPU5TP/4FP/0FN, Groq source-adopted0TP/2FP/5FN under frozen literal aliases. Quantity-bearing entity strings and empty responses are not repaired after evaluation. AI adoption/Shadow remains **HOLD**, not an accuracy or forecasting PASS. The other12 eligible documents without generation are AUTH-wait/unattempted, not model false negatives. The source-valid advisory, original model role, downstream engine event and candidate counts stay separate.

Collection-only research automation uses the existing `SourceClient`/SQLite ledger, isolated new/failed URL queues, exact source versions and a bounded daily refresh. Its child environment excludes AI keys. Three actual local timer executions stored9 additional native snapshots; these are outside the frozen20 and their independent publication/meaning reviews remain pending. It performs **zero AI calls**, has no operating UI/alert integration, and is not qualified seven-day AI Shadow. Local host lifetime/fresh-task restoration is unverified. The original seven-day stop time is preserved across research-process restarts. Start instructions were saved as a cloud configuration **draft only**; review/save/publish is required for future environment application. No network/credential/protected schedule setting was changed.

Offline current-result replay (no requests or CPU inference):

```bash
.venv/bin/python tools/v4_round2_replay.py
```

Resume the unchanged evaluation only after external validation of the existing Secret binding/settings; never paste a key into Git/logs or repeat the invalid credential request. Changing inference rules after inspecting these results consumes this evaluation for that version; new independent performance evidence then needs other unused documents.

## Historical offline quote/role follow-up (2026-10-14)

Plan v1.7 starts at `594d233702de4234cd4e06f88dea26ac060d2fe1`. New Groq POSTs/tokens/API cost are **0/0/$0**. Existing installation, source corpus and CPU baseline are reused; no model preparation or inference is needed. Seven original rejected items remain rejected after exact read-only diagnosis. The research adapter now rejects model prefixes and unproven ordered-object relations, keeps actual equipment orders separate from future output capacity, and records raw-model/source-checked/engine roles separately. FOX-XP's existing demand correction is retained, not counted as a newly discovered fact.

Current-instance offline command: `.venv/bin/python -m scripts.v4.quote_role_diagnostics`. It needs the retained `var/v4/repair` evidence and `var/v4/quote-followup` preservation/before receipts; it uses no API calls. The original response/score artifacts and frozen20 remain unchanged and consumed. The earlier `replay_repair_evidence` freeze guard intentionally rejects a changed adapter; its successful replay at the original SHA is historical evidence, not evaluation of the current adapter. The follow-up uses a hash-verified in-memory copy of the old adapter only for paired synthetic comparisons, without resetting the checkout. HTTP400's exact cause remains UNKNOWN/BLOCKED; do not retry it.

## Historical repair/evaluation at 594d233 (2026-10-14)

The approved scope is plan v1.6. Stages 1–3 remain PASS. The original 118 documents and frozen50/source hashes/split are unchanged. Native recovery obtained 13 new HTML captures whose parsed bodies exactly match the frozen text; one changed version was retained separately. This is not recovery of historical HTML. FULL30/PARTIAL20 remains the original corpus classification.

Public input reviews separate source/date/native hashes from transmitted spans. Only a verified terminal public press-contact footer may be excluded; secrets anywhere, explicit restrictions and unknown URL parameters remain blocked. EIA's single decimal `id` is allowed only on the verified official article endpoint. Whole paragraphs and adjacent caveats are retained; oversized contexts are held. All50: eligible29, held13, blocked8. Scope and reasons: `stage4-corpus/safe-inputs-v1.json`.

The small research adapter preserves original AI outputs and feeds separately verified events to the unchanged engine. LIVE/operational integration stays disabled. One real development response passed source validation and supplied one order event to an engine observation; incomplete TARGET and missing independent supply yielded no research bottleneck candidate. Synthetic positives and adverse cases are distinct from real findings.

New requests: **8 POSTs**, **6,242 input + 2,809 output = 9,051 reported tokens**, Free Plan **$0**; **one HTTP failure has unreported token usage**. Seven responses were received including the successful development response. Evaluation stopped at HTTP400 `invalid_request_error`, flags=[]; its detailed provider cause is UNKNOWN because raw error text is not retained. Six earlier evaluation responses failed strict source validation. No same-input retries or additional calls were made. One shared rolling budget includes the five historical attempts; changing run IDs cannot reset it.

Evaluation is limited to frozen excerpts and AI source review, not human verification or full-document accuracy. Pipeline adoption on six response documents: TP0/FP0/FN38; precision undefined, recall0. Raw literal/alias scoring has separate context and name-mapping limitations. CPU comparison uses newly computed pinned GLiNER2 product entities on the same six inputs, not historical output. General improvement and independent adoption criteria remain unmet. See `STAGE4_RESULTS.json` and `PROGRESS.json` for review limitations and resume points.

A further source-only AI session wrote its blind draft before reading the existing gold. It checked nine documents/14 windows: 81 of 83 PRESENT relations were supported with their stated scope; two remain unresolved in an unattempted document. Nine previously ambiguous facts remain ambiguous. This is a source audit, not a gold-agreement accuracy estimate or human verification. Original review sessions' status-metadata exposure is retained in the record. Gold and scored denominators were not changed after evaluation.

Lightweight test setup is `python -m pip install -e '.[test]'`; it excludes model weights/torch. The selected CPU model was prepared once in `var/v4/repair/cpu/env` with pinned, checksum-verified weights in `var/v4/repair/cpu/runtime`. Reuse it; model preparation is not a startup/test prerequisite.

Offline evidence replay (no network, keys or model runtime):

```bash
cd /workspace/bottleneck-control-tower
.venv/bin/python -m scripts.v4.replay_repair_evidence
```

Do not rerun evaluation preparation/freeze or a live request to seek a better result. Preserve the recorded freeze and HTTP contract block. Further source-quote or scoring work must use development evidence first and retain the consumed evaluation history. Seven-day Shadow, operating Actions/DB, main and alerts remain untouched. The sections below are historical evidence, not current usage or current blockers.

## Historical stage 3 functional verification

Stage 2 remains fixed PASS. The request schema, prompt, input/cache keys, exact quote validator and CPU engine were preserved. `semantics.py` reviews source-verified facts: money requires separate physical quantity evidence, customers require actual product purchase/delivery relations, and supplier pools require actual product qualification. Plans, forecasts, negation, relief, project/product/equipment/slot types and product-specific quantity/time/region/specification relations are checked. Rejected meanings stay null with the original source fact retained in the audit; no S-stage promotion occurs.

**Stage 3 functional PASS:** 85 new authored/official-response cases and 37 selected existing cases passed; broad 99/261 suites were not repeated. A manually reviewed, hash-identical official source and its three saved actual response items were reused. Across 23 selected fields: 8 correct known adoptions, 0 incorrect adoptions, 15 UNKNOWN (including three role labels); two separate literal mention omissions remain (Westinghouse technology name and U.S. region). The prior processed response had two incorrect adoptions: funding quantity and recipient/customer. This is one-source development verification; general accuracy remains UNKNOWN.

New generation calls **0**, new tokens **0**, cost **$0**. Separate stage-3 SQLite copy `var/v4/stage3/replay` stored the reprocessed job and review. Fresh-process/cache and backup checks preserved the two semantic holds and all seven source references. The stage-2 source ledger was opened read-only. The 50-document comparison and Shadow remain NOT_RUN. Details: `STAGE3_RESULTS.json`.

## Historical stage 2 completion (2026-10-14, PASS preserved)

Continued from `599c4b7df9c2290f0c626b74f93e42c39f83e9f3`. The wire JSON schema exactly matches the previously accepted version. Runtime code, Python quote binding, original/response hashes and saved tests were reused unchanged. Local preflight reserved 6,124 under the 6,400 cap; no model/auth/setup queries or reinstall were repeated.

Exactly **one** new Groq Free generation succeeded: **904 input + 701 output = 1,605 tokens, $0**. All **3/3 items and 7/7 nonempty quotes** passed exact unique source matching within the same reviewed 600-character excerpt. The model still supplied incorrect coordinates; Python discarded all seven and calculated strict verified ranges. Raw response, validation and accepted cache were stored in SQLite. Separate processes reopened the live ledger and backup, with identical results and **zero additional network calls** during cache reads.

**Stage 2 connectivity and grounding PASS; general semantic accuracy UNKNOWN.** The existing guard identifies the named fuel-line Projects as a PROJECT and SMRs as a PRODUCT_FAMILY, while funding/partnership roles stay UNKNOWN. Remaining semantic review: `$800 million` is funding rather than product quantity, TVA/Holtec are stated funding recipients rather than established product customers, and the Westinghouse technology name was omitted. No S-stage promotion, stage 3 evaluation or Shadow was started. See `GROQ_QUOTE_REPAIR_RESULTS.json` → `current_live_result` / `current_live_artifacts`.

The prior 38 quote tests and 25 affected regression cases were reused with unchanged code/evidence hashes; the historical 99 and 261 suites were not rerun. Prior mock WAIT_API/restart evidence is separate from the newly verified real cache/SQLite results. Live quota exhaustion was not induced. Full-document completeness and unavailable historical CPU comparison remain separate limitations.

## Prior quote repair (preserved history)

Python now binds exact unique quotes and discards every model coordinate. Saved original/response hashes matched; one SMR item passed strict source verification and was stored as PRODUCT_FAMILY with role UNKNOWN. Four invalid alias/null-evidence items remain rejected. General semantic accuracy is UNKNOWN. New tests: 38 PASS; selected existing tests: 25 PASS; prior 261 core regression passes reused without a whole rerun or reinstall.

That earlier task's one permitted live request returned HTTP 400 / invalid_request_error / SCHEMA. No new response or token usage was received; no retry was made. The exact formerly accepted wire schema was then restored; start/end are untrusted compatibility fields while Python computes all real coordinates. Its real recheck was NOT_RUN within that earlier task's exhausted allowance. That historical stage-2 BLOCKED result is preserved under `prior_live_result` in `GROQ_QUOTE_REPAIR_RESULTS.json`; the subsequent one-call success above completes the remaining connection/grounding check.

## Prior connection trial (preserved history)

`openai/gpt-oss-20b` remains selected. Official model listing returned it active with structured-output support; official docs confirm strict JSON and Free quotas. The user confirmed “Free Plan이다”. Existing `GROQ_API_KEY` and secure `api.groq.com` binding were reused; no key value was written or requested.

Generation POST attempts: **3** in separate bounded runs, **2 errors**, **1 actual JSON response** saved in SQLite `API_RECEIVED`. Measured usage: **843 input + 1,139 output = 1,982 tokens**. Earlier failed-request tokens: **UNKNOWN**, not zero. API cost $0 on the user-confirmed Free Plan; no independent billing-account audit was performed. Metadata GETs are separate: one model-list success and one default-client diagnostic failure.

**Connection/storage PASS; source-valid output FAIL; overall stage 2 is not PASS.** Wrong offsets, non-literal product aliases and non-empty evidence for null values caused all five proposed items to be held. Zero accepted readings/S3. The model called `advanced light-water SMRs` a PROJECT and treated funding/partnership actions as supply increases; these do not prove increased delivered supply. This 600-character smoke is not a formal accuracy or lead-performance evaluation. Do not start stage 3 or seven-day Shadow.

Full public response, failures and the ten requested checks: `GROQ_STAGE2_RESULTS.json`.

## Quotas and runtime

Official defaults: 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD. Latest actual headers: RPD **1,000**, TPM **8,000**, remaining requests **999**, remaining tokens **6,702** (earlier response: 6,756). RPM/TPD are published conservative caps, not observed account overrides. Other organization traffic is not visible locally.

Tracked `config/v4-free-ai.json` remains disabled and its generic account unverified. Current ignored configuration: `var/v4/groq-stage2/trial-config.json`, with dated user Free confirmation and quota evidence. Verification expires after seven days. Do not activate an account merely from public pricing or create another key.

Caps per run: one POST, reservation 6,400, output 2,048 tokens, input 600 characters, up to two windows, 60-second timeout. Reservation is UTF-8 payload bytes plus output cap, not measured tokens. Local quotas use 80% and rolling 24-hour accounting. No automatic SDK retry, redirect, repair, search, grounding or paid tools. Remote low-quota headers apply even when source validation rejects a response.

## Sources, storage and validation

Prior V4 SQLite/original/CPU readings and pinned CPU weights were absent. Two official pages were **newly acquired**, not restored. Energy.gov canonical/publisher/publication/raw and body hashes passed, while full-document completeness remains PARTIAL/BLOCKED. A hash-bound explicit public-excerpt review allowed bounded public text only; it did not promote original provenance or an S stage. EIA lacked canonical/publication evidence and stays held. A third issuer fetch was blocked and not looped.

Native HTML, unchanged original bodies, reviews, responses, attempts/errors/jobs and backups remain in ignored `var/v4/groq-stage2/`. Fresh processes and backup restore retained the real response/REVIEW_REQUIRED with no new API calls. A separate clearly marked simulated-429 ledger retained WAIT_API/cooldown. Real quota was not deliberately exhausted. Success-cache/alias tests passed mocks; no valid live reading exists for a live success-cache claim. CPU same-input numerical comparison is BLOCKED; existing engine code is unchanged and no large reinstall was attempted.

Executed: **99 functional passes**, **261 existing regression passes + 1 existing real-holdout skip**. Commands overlap on V4 integration tests; do not add them as distinct-test totals. Evidence: `GROQ_FUNCTIONAL_TESTS.xml`, `GROQ_REGRESSION_TESTS.xml`.

## Supported corrections and remaining work

Default urllib reproduced 403/1010 on a read-only request; the identifying BCT client succeeded. Requests now identify the real client as `BCT-V4-stage2/1.0`, without browser impersonation, alternate proxy or policy bypass. The wire schema uses documented strict structural types, retaining local cardinality checks, with documented `reasoning_effort=low`.

The old adapter did not retain the second POST HTTP detail; its exact rejecting parameter is unknown. The next changed-contract request returned JSON. New errors retain only HTTP status and recognized safe diagnostic labels, never raw credential-bearing error text. Unchanged invalid contracts remain held; only a changed contract may reopen an INPUT_INVALID hold. Received usage and transport recovery are saved independently of source validation. A null unverified `checked_at` now returns WAIT_API safely.

The quote/offset contract, real SQLite verification and stage-3 meaning guards are complete. The next separately authorized development step is stage 4's official-source comparison. General accuracy remains UNKNOWN. TARGET's five fields/S1/S2/S3 are unchanged. This task ends at stage 3; main, V3.3 operating DB, Actions and alerts were not changed.

Local inspection without network:

```bash
cd /workspace/bottleneck-control-tower
.venv/bin/python -m bct.v4 --root var/v4/groq-stage2/live status
```

Do not repeat the live trial to seek a desired answer. Wrong-source jobs stay REVIEW_REQUIRED; unavailable Groq stays WAIT_API. Collection stays separate and sources are retained.

Official checks: [Free quotas](https://console.groq.com/docs/rate-limits), [structured outputs](https://console.groq.com/docs/structured-outputs), [API reference](https://console.groq.com/docs/api-reference), [billing](https://console.groq.com/docs/billing-faqs), `GET https://api.groq.com/openai/v1/models`.

Environment allowlist draft retains `api.groq.com`, adding `console.groq.com`, `www.energy.gov`, `www.eia.gov`, `investors.bakerhughes.com`; existing package presets stay intact. Draft save confirmed; publication unverified. Review/save the draft in environment settings and publish to retain prepared current-instance filesystem/configuration for future tasks. Observed successful source/console requests and the blocked issuer request do not prove that draft saving itself applied or published the network policy.
