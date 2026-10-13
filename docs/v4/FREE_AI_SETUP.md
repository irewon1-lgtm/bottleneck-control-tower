# Stage 2 — GroqCloud only, Gemini disabled

Updated 2026-10-14 (Asia/Seoul). Read `EXECUTION_PLAN.md` and `PROGRESS.json` first. The fixed eight-stage goal and CPU GLiNER2 engine remain unchanged. Active AI: **GroqCloud Free Plan only**. Gemini code is retained, but routing/probes and key requirements are disabled. No third provider, paid fallback, upgrade or billing action.

## Current real result

`openai/gpt-oss-20b` remains selected. Official model listing returned it active with structured-output support; official docs confirm strict JSON and Free quotas. The user confirmed “Free Plan이다”. Existing `GROQ_API_KEY` and secure `api.groq.com` binding were reused; no key value was written or requested.

Generation POST attempts: **3** in separate bounded runs, **2 errors**, **1 actual JSON response** saved in SQLite `API_RECEIVED`. Measured usage: **843 input + 1,139 output = 1,982 tokens**. Earlier failed-request tokens: **UNKNOWN**, not zero. API cost $0 on the user-confirmed Free Plan; no independent billing-account audit was performed. Metadata GETs are separate: one model-list success and one default-client diagnostic failure.

**Connection/storage PASS; source-valid output FAIL; overall stage 2 is not PASS.** Wrong offsets, non-literal product aliases and non-empty evidence for null values caused all five proposed items to be held. Zero accepted readings/S3. The model called `advanced light-water SMRs` a PROJECT and treated funding/partnership actions as supply increases; these do not prove increased delivered supply. This 600-character smoke is not a formal accuracy or lead-performance evaluation. Do not start stage 3 or seven-day Shadow.

Full public response, failures and the ten requested checks: `GROQ_STAGE2_RESULTS.json`.

## Quotas and runtime

Official defaults: 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD. Actual headers: RPD **1,000**, TPM **8,000**, remaining requests **999**, remaining tokens **6,756**. RPM/TPD are published conservative caps, not observed account overrides. Other organization traffic is not visible locally.

Tracked `config/v4-free-ai.json` remains disabled and its generic account unverified. Current ignored configuration: `var/v4/groq-stage2/trial-config.json`, with dated user Free confirmation and quota evidence. Verification expires after seven days. Do not activate an account merely from public pricing or create another key.

Caps per run: one POST, reservation 6,400, output 2,048 tokens, input 600 characters, up to two windows, 60-second timeout. Reservation is UTF-8 payload bytes plus output cap, not measured tokens. Local quotas use 80% and rolling 24-hour accounting. No automatic SDK retry, redirect, repair, search, grounding or paid tools. Remote low-quota headers apply even when source validation rejects a response.

## Sources, storage and validation

Prior V4 SQLite/original/CPU readings and pinned CPU weights were absent. Two official pages were **newly acquired**, not restored. Energy.gov canonical/publisher/publication/raw and body hashes passed, while full-document completeness remains PARTIAL/BLOCKED. A hash-bound explicit public-excerpt review allowed bounded public text only; it did not promote original provenance or an S stage. EIA lacked canonical/publication evidence and stays held. A third issuer fetch was blocked and not looped.

Native HTML, unchanged original bodies, reviews, responses, attempts/errors/jobs and backups remain in ignored `var/v4/groq-stage2/`. Fresh processes and backup restore retained the real response/REVIEW_REQUIRED with no new API calls. A separate clearly marked simulated-429 ledger retained WAIT_API/cooldown. Real quota was not deliberately exhausted. Success-cache/alias tests passed mocks; no valid live reading exists for a live success-cache claim. CPU same-input numerical comparison is BLOCKED; existing engine code is unchanged and no large reinstall was attempted.

Executed: **99 functional passes**, **261 existing regression passes + 1 existing real-holdout skip**. Commands overlap on V4 integration tests; do not add them as distinct-test totals. Evidence: `GROQ_FUNCTIONAL_TESTS.xml`, `GROQ_REGRESSION_TESTS.xml`.

## Supported corrections and remaining work

Default urllib reproduced 403/1010 on a read-only request; the identifying BCT client succeeded. Requests now identify the real client as `BCT-V4-stage2/1.0`, without browser impersonation, alternate proxy or policy bypass. The wire schema uses documented strict structural types, retaining local cardinality checks, with documented `reasoning_effort=low`.

The old adapter did not retain the second POST HTTP detail; its exact rejecting parameter is unknown. The next changed-contract request returned JSON. New errors retain only HTTP status and recognized safe diagnostic labels, never raw credential-bearing error text. Unchanged invalid contracts remain held; only a changed contract may reopen an INPUT_INVALID hold. Received usage and transport recovery are saved independently of source validation. A null unverified `checked_at` now returns WAIT_API safely.

Next: fix the exact quote/offset contract using the saved response first, then require a source-valid stored live reading in a new bounded run. Do not relax citation checks, rewrite invented aliases to get PASS, or change TARGET's five fields/S1/S2/S3. Missing facts remain UNKNOWN. No more API calls occurred after the received response. Main, V3.3 operating DB, Actions and alerts were not changed.

Local inspection without network:

```bash
cd /workspace/bottleneck-control-tower
.venv/bin/python -m bct.v4 --root var/v4/groq-stage2/live status
.venv/bin/python -m pytest -q tests/test_v4_free_ai.py tests/test_v4_integration.py
```

Do not repeat the live trial to seek a desired answer. Wrong-source jobs stay REVIEW_REQUIRED; unavailable Groq stays WAIT_API. Collection stays separate and sources are retained.

Official checks: [Free quotas](https://console.groq.com/docs/rate-limits), [structured outputs](https://console.groq.com/docs/structured-outputs), [API reference](https://console.groq.com/docs/api-reference), [billing](https://console.groq.com/docs/billing-faqs), `GET https://api.groq.com/openai/v1/models`.

Environment allowlist draft retains `api.groq.com`, adding `console.groq.com`, `www.energy.gov`, `www.eia.gov`, `investors.bakerhughes.com`; existing package presets stay intact. Draft save confirmed; publication unverified. Review/save the draft in environment settings and publish to retain prepared current-instance filesystem/configuration for future tasks. Observed successful source/console requests and the blocked issuer request do not prove that draft saving itself applied or published the network policy.
