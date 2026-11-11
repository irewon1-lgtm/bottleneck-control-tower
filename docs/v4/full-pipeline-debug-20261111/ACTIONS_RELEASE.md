# Actions/release evidence — 2026-11-11

Task `BCT_V4_FULL_PIPELINE_DEBUG_20261111`; plan `BCT-V4-Q-1.0`, Q2. Development baseline `23a0615f1a10f2b938cb2b5401706a1995b4d4f2`; observed main `28d0b8c648c0218ab2e74a1fa04ca8d63e659933`. This is evidence for the existing plan, not a new progress ledger. Objective Lock and historical verdicts are preserved. Evidence: [ACTIONS_RELEASE.json](ACTIONS_RELEASE.json).

## Actual Future failure and exact tree mismatch

[Latest Future run 42944587807](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42944587807), scheduled on 2026-11-11, fails in `Verify actual code release gates before automatic candidates`. Its actual log ends with `ValueError: validated code/test file set changed or missing`; regression, screening, CPU and sidecar publication steps are skipped. [Earliest failure in the supplied seven-day snapshot, 41756307135](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/41756307135), has the same failed step and exact error. The snapshot has 58 Future runs, 57 failures. Only these two failure logs were inspected; the other 55 failures share the same main SHA but are not independently assigned this exact cause.

The release receipt binds [recovery run 38331945733](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38331945733) to `1e4ec2aaed3cba0a627d31e28c613c8490a27b50`. Its eight required storage/source/reading/corpus/E2E steps really completed successfully. Artifact `11783493914` is unexpired at inspection and its digest matches the recorded `00ac5d87109c6c365f9d2a19fe2f15a83919012ed012222f9b4932fd5d70243a`. **It expires 2026-11-12 01:47:21 UTC.** These are historical results for that code, not current main validation.

Using the guard's exact path policy, the validated tree has 235 files and main has 238:

| Difference | File |
|---|---|
| Added | `.github/workflows/v4-cpu-main-cache-seed.yml` |
| Added | `.github/workflows/v4-cpu-private-research.yml` |
| Added | `.github/workflows/v4-cpu-private-settings-check.yml` |
| Changed | `.github/workflows/ui-pages.yml` |
| Missing | None |

The Pages change replaces canonical-data snapshot publication with V4 integration-branch export/build/deploy and changes its triggers. Its validated blob is `eddcbbf87c97269e7aa814bb77750cfb4ef37866`; current main blob is `7a3bd725db8bf48a9f57070c57bb462bf96efd7b`. All other shared covered blobs match. Thus fixing only the three-file set would still leave a covered hash mismatch. The guard is correctly refusing unvalidated code; no guard exception is justified.

An isolated replay used fetched immutable Git objects and actual API run/job/artifact metadata. The recorded validated tree returns `PASS` for 235 files; exact current main reproduces the production refusal. This does not rerun or relabel Gates 0–6. The existing `tools/v4_release_revalidate.py` also refuses current main with `REVALIDATION_SCOPE_CHANGED_NOT_THE_THREE_ADDITIONS`. Its workflow checks out older `14c2de54...`, so a prior read-only success cannot validate `28d0b8c6...`.

## CPU skip, configuration and recovery prerequisites

[CPU run 42942892160](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42942892160) is `workflow_run` on main. Both `research` and `publish` are skipped with no steps executed. Research requires reviewed execution pin `221fa92b1cbff8950716ec373eac793ca340c873`, explicit enabled=`true`, a main consumer event and a successful main acquisition parent; publish depends on research success. The nearest preceding acquisition `42939818925` succeeds and its log binds RSS `42939431146`. Run metadata does not expose the skipped job's complete event payload, so this temporal pairing is not proven schedule-chain validation.

Current variable values are **UNKNOWN**: the root's variable-read attempt returned HTTP403 and was not repeated. Stored October evidence has enabled=`false`, code=`da7cb9bc...`, expected pin=`221fa92b...`; these are historical values. The exact currently false conjunct cannot be recovered from a skipped job alone. No variable, Secret or pin was changed.

Two live read-only APIs independently show **zero caches and zero cache bytes**. Both mandatory runtime/model cache and encrypted private-state bridge cache are absent now. The consumer deliberately uses `fail-on-cache-miss: true`, offline flags and no install fallback. Missing cache is an additional activation blocker, not the cause of a job that never started.

Recovery must preserve the existing model/pin, source-separated state, private CAS and 8-table/hash checks. Recover an absent/stale bridge from the latest durable private state with reviewed `bridge-recover`; do not reseed or create empty state. `verify_predecessor` also checks the preceding successful publisher/run attempt before model loading. Bridge recovery writes private state/cache and was not dispatched in this development-only task. Runtime recovery must first locate an approved reusable exact runtime; the scheduled path must not gain a download/install fallback.

First actual scheduled new reading + source validation + verified private persistence ACK remains unexecuted here. No seven-day observation was started. A manual recovery or empty queue cannot count as successful scheduled observation.

## Minimum legitimate release revalidation

1. Freeze the exact intended operating tree, explicitly including all four differences above. Do not set a documentation/development SHA as the CPU execution pin.
2. Obtain source-access/corpus inputs; preserve hashes, judgments, original DB/history and completed-reading receipts. Original fixed230 run `37790294699` now returns `artifacts: []`, so its old download step cannot supply the required corpus. Locate a permitted intact copy before claiming real-source QA.
3. Execute the required Gates 0–6 on that exact tree: real GitHub storage, source access/inventory/verification, actual reading/atomic queue recovery, fixed230 and full regression/quality checks. Reuse permitted exact inputs and completed receipts; missing actual executions stay blocked. Existing Gate 1 creates/probes a remote branch and Gate 5 publishes the operating queue, so current development-only/no-operational-write authorization does not permit dispatching this workflow.
4. Only after that real successful run, bind exact SHA, run ID, unexpired artifact ID and digest in a reviewed receipt and separately authorize/apply the operating release. The unchanged guard requires the exact workflow, all required steps, artifact/run binding, complete file set and matching blobs. A receipt-only change or workflow exclusion would bypass the contract. Read-only checks do not replace it.

These are required actions, not completed gates. The older run and expiring artifact remain historical evidence.

## Verification and prior audit

Executed outside the restricted subprocess sandbox so GPG/local socket tests could run:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_operating_release_guard.py tests/test_v4_cpu_research_workflow.py tests/test_v4_cpu_operations.py tests/test_v4_private_state.py
```

Result: **51 passed in 8.06s**, exit 0. Tests cover fail-closed release conditions, workflow guards, authenticated restore/hash/CAS/stale bridge and observation guards; they do not establish inference accuracy or scheduled operation.

Reproduce with the two immutable Git objects locally available:

```sh
PYTHONPATH=src .venv/bin/python docs/v4/full-pipeline-debug-20261111/reproduce_actions_release.py
git diff 1e4ec2aaed3cba0a627d31e28c613c8490a27b50 28d0b8c648c0218ab2e74a1fa04ca8d63e659933 -- .github/workflows/ui-pages.yml
```

The missing validation object was obtained with `git fetch --no-tags --depth=1 origin 1e4ec2aaed3cba0a627d31e28c613c8490a27b50`; this changes local objects/FETCH_HEAD only, not a remote branch. The replay extracts temporary copies and performs no network calls or operational writes.

Prior commit `2aaaa91f17ea1c29eb7a36c4cd26783e405610b9` was read with `git show`, including report, minimal-fix specification and verification receipt. It adds 14 audit evidence files; no production source/workflow changes. Its verdict is explicitly `PARTIAL_BLOCKED`: two real extraction misses in the accessible seven-body replay, complete TARGET/pairs 0, full latest DB recount blocked. It validates neither CPU activation nor current release. Those limits remain intact.

Changes here: evidence/report/reproducer only. Guard, CPU workflow/pin, variables, Secrets and operating data unchanged. Model inference/download/install, external AI, operational dispatch/write, commit and push: **0**. Next action: carry these blockers in the existing progress ledger while completing authorized development fixes; later release/recovery application needs the concrete prerequisites above.
