# Stage 2: free API connection, operating use remains disabled

Read EXECUTION_PLAN.md and PROGRESS.json first. The fixed sequence is Gemini then
GroqCloud, not xAI Grok. This branch adds optional annotations to existing V4;
it does not replace V3.3 or change its Actions, databases, alerts or S stages.

## Fixed models and official conditions

Checked 2026-10-13 against official documentation:

| Provider | One fixed model | JSON | Free condition |
| --- | --- | --- | --- |
| Gemini Developer API | `gemini-3.5-flash-lite` | GenerateContent `responseMimeType` and `responseJsonSchema` | Pricing lists free input/output on Free Tier; account/model quotas must be checked in AI Studio |
| GroqCloud | `openai/gpt-oss-20b` | Chat Completions strict JSON Schema | Free Plan; published base limits 30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD; account limits can differ |

The Groq model is served only through `api.groq.com`. No OpenAI API or third
provider is used. Neither account's free access or exact quota was verified in
this execution: no credentials were injected. Models are pinned from official
docs; account eligibility and live model availability remain BLOCKED.

Sources: [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[pricing](https://ai.google.dev/gemini-api/docs/pricing),
[billing](https://ai.google.dev/gemini-api/docs/billing),
[quotas](https://ai.google.dev/gemini-api/docs/rate-limits),
[REST generation/schema](https://ai.google.dev/api/generate-content),
[Groq free quotas](https://console.groq.com/docs/rate-limits),
[Groq structured outputs](https://console.groq.com/docs/structured-outputs),
[Groq billing](https://console.groq.com/docs/billing-faqs).

## One setup request for the user

1. Create keys in an actual Gemini **Free Tier project without billing** and
   a GroqCloud **Free Plan account**. Do not upgrade or attach payment.
2. Store keys using the existing secure secret injection route. GitHub repository
   secret names are `GEMINI_API_KEY` and `GROQ_API_KEY`. For a Work/Codex execution,
   inject the same environment variable names through that environment's secret
   settings. GitHub repository Secrets do not automatically become Work variables.
   Never paste keys into chat, config files, commands, commits or logs.
3. Confirm each selected model is enabled and has a nonzero free quota. Supply
   the free-tier and limits screen (with keys/account identities hidden), or its
   values for RPM, RPD, TPM and TPD if applicable. Do this for both providers at once.
4. Restore the **existing V4** SQLite snapshot into a separate development root
   with its captured public originals and prior CPU readings. Never use the V3.3 DB.

The execution environment must permit the two official API hosts
`generativelanguage.googleapis.com` and `api.groq.com`. The current workspace
has restricted outbound access and that API access was not verified. Do not
bypass an environment/organization denial through another provider. Prior V4
delivery records a rejected environment allowlist update and a GitHub PR 403;
neither blocked mutation is repeated without changed permission evidence.

Keep `config/v4-free-ai.json` disabled in Git. Make a runtime copy under ignored
`var/v4/`, set `enabled=true`, and fill each account: `verified_free=true`,
`tier="Free"`, exact fixed `model`, timezone-bearing `checked_at`, evidence path,
`settings_revision` and observed positive RPM/RPD/TPM (TPD can be null if absent).
Confirmation expires after seven days; paid/unverified/stale accounts cannot call.
Changing verified settings/key identity is required to reopen an AUTH/zero-quota block.
This is a local safeguard, not a billing-account API verification.

Use the existing environment; no provider SDK or new dependency is needed:

```bash
PYTHONPATH=src python scripts/v4/api_trial.py --root var/v4/isolated-runtime --config var/v4/free-ai-config.json
PYTHONPATH=src python -m bct.v4 --root var/v4/isolated-runtime api-read --config var/v4/free-ai-config.json --limit 3
```

The trial checks Gemini and Groq separately, once per unchanged input/provider,
as explicit connectivity probes. Normal `api-read` and optional `cycle --api-config`
always use the fixed fallback order. Do not schedule these or change Actions in
this task. Source collection is not run by `api-read`.

## What the implementation verifies

Exact source quotes/character positions, body hashes, the original publication
metadata, and literal field values are checked locally. API classifications are
advisory and retain semantic UNKNOWN. Five TARGET fields stay `product`,
`specification`, `region`, `customer_group`, `supply_pool`. No automatic S3 promotion.
The original CPU GLiNER2 remains available. API reads original windows directly
and can find products absent from CPU spans. Unselected body text is retained and
reported as unprocessed; bounded windows are not full-document analysis.

Public provenance is required. Query-bearing URLs, private/forbidden markers,
credentials, personal contacts and account-like material are held for review.
Safety/organization policy denials and bad requests never trigger provider hopping.
An unsupported request contract is also held across documents/restarts until
that local request contract changes.
HTTP makes one POST with a 60-second timeout, no redirect, SDK retry, search,
grounding, paid tool or repair request. FORMAT/SOURCE errors can try the unused
second provider once. Normal UNKNOWN is a successful answer and is never retried.

SQLite records attempts before IO, responses, usage, jobs and provider blocks.
Restart and backup preserve these records. An interrupted uncertain request is
held instead of being automatically resent. Successful duplicate input is cached,
including alias URLs; source identity is reattached during cache validation.
Local quotas reserve byte-count plus output-cap budgets (conservative estimates,
not actual tokens) and apply 80% of confirmed limits. Sliding 24-hour limits are
deliberately stricter than daily reset; Gemini RPD reset is Pacific midnight.
Remote low-quota headers stop a provider too. Failed-request token usage can be UNKNOWN.

Transient failures without a provider resume time wait at least an hour; known
daily exhaustion without a reset waits 24 hours. A provider-supplied Retry-After
is honored. Recovery uses one bounded check in the next normal execution. Both
unavailable means WAIT_API; it neither deletes sources nor writes analysis complete.

Functional mocks, live connectivity, semantic accuracy and EARLY performance are
different results. Stage 3+ and seven-day Shadow observation are NOT_RUN here.
