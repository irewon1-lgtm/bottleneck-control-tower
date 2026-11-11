# Gate preparation after approved PR44 — 2026-11-11

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`; existing plan `BCT-V4-Q-1.0`/Q2. [PR45](https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/45) is open, ready for review and **not merged**. The root's explicit approval question is pending. **USER_APPROVAL_REQUIRED** for the new main merge and for actual Gate execution with the effects below. Merge-only approval does not authorize a Gate run. Scheduled V4 CPU remains OFF. No full Gate was dispatched by this preparation.

Head `8ae9fb8716ed211a317481fbe93e8062898c91d3`, tree `4127ea0156c42ac4b8615f485115b9751ce63483`, base main `e31743a91ab3604421ec7c35796dfda8f63dd51f`. The root ported the same three-file fix to development as `faa90b9`. This evidence file does not replace or edit `PROGRESS.json`.

The three changed files are `.github/workflows/bct-recovery.yml`, `.github/bct-recovery-request.json` and `tests/test_recovery_fixed230_workflow.py`. The known expired source run `37790294699` is replaced with the already tested immutable helpers `7d9188608a66520115727ff5daa30d13190f4958`, saved RSS run `42939431146` and source run `42939818925`. Artifact ID/size/digest/expiry and the literal RSS manifest hash are checked before reception; the source receipt is checked again before the exact corpus copy. The fixed fingerprint remains `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec`.

The required `Restore original 230-source regression corpus` step name, all Gate conditions, guard, operating release receipt, frozen engines, Qwen configuration, batch bounds and CPU settings remain unchanged. Only the stale request reason changes; its 19 root-file pins and full cache inventory remain intact.

## Verified tests and saved inputs

Five new regressions failed against the expired downloader first. Initial recovery/guard/transport checks passed 23 tests; the expanded related set passed 30. Final local regression passed **1020 Python tests with 1 existing independent-holdout skip** in 25.09s and **34 JavaScript tests**. All 7 new contract/real-shell tests passed; independent review reproduced 7 passes in 0.76s and found no new blocker. Diff checks and new-test Ruff F checks passed.

Exact-head GitHub CI passed twice: [push run43002046730](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43002046730) and [PR run43002162715](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43002162715). The seven source-QA core files are byte-identical to `018f...`, whose actual exact230 QA passed in run `42995363348`. The 4.6GB source download and real source QA were not repeated to prepare this PR.

| Saved input | Exact binding | Expiry UTC |
|---|---|---|
| Source run42939818925 | Artifact13821760877; 4,598,165,007 bytes; digest `949e95d2efda7a3fd3e7a124eb0d6569b56b54dcd1a3d5fd7f053dc75b8dfb72` | 2026-12-11 01:48:44 |
| RSS run42939431146 | Artifact13820246103; 527,551 bytes; digest `006124e204a8315e68e9a8abbd39cbca8eacc523e09d89318fbe1d830e2f403a` | 2027-02-09 01:30:22 |
| Recovery run38331945733 | Artifact11783493914; 45,073,105 bytes; digest `00ac5d87109c6c365f9d2a19fe2f15a83919012ed012222f9b4932fd5d70243a` | **2026-11-12 01:47:21** |

The old recovery ZIP remains hash-verified locally. A preserved local copy does not bypass its API expiry. Recheck availability immediately before any approved dispatch; do not knowingly start the expired path after the deadline.

## Actual paired backup and local Gate1 preview

The read-only preflight used 26 GitHub GETs, no mutations. Both authoritative roots were assembled from the single immutable future-data generation below and saved under `/tmp/bct-operations-recovery-20261111/pre-gate-backup`. The current configured preservation baseline and the old resume artifact's seal both passed against this pair.

| Ref | Before and after read-only checks |
|---|---|
| main | `e31743a91ab3604421ec7c35796dfda8f63dd51f` |
| data | `064ab2d22b78cbf377e09f1c2b80cd1fe00fa9c7` |
| future-bottleneck-data | `8730f5cdec9c7f6eb624df1c6d40a76b2b5d1bfe` |
| ops/recovery-20261010 | `a461cc7787d588a28c8d17a7a94ae81c9f0bdf9c` |

Candidate root blob `faf0b378a33a629145eb1f7218d58369280fe87e` reconstructs 231,980,251 bytes with SHA256 `155626b86c8f9b41e9ee154cb6a927725ad53921b7c29d53e02add928c8e97e0`. Tracking root `adbec29fe290ff6a131c792861e564a15577c989` reconstructs 10,939,744 bytes with SHA256 `98cd3bb00bb2632072079f209891a5f3c2e6cbe9c4e31a0324ee1684c13817a9`. Canonical DB/previous/state blob IDs and sizes are recorded in [GATE_PREPARATION.json](GATE_PREPARATION.json). Source text/DB contents are not copied into Git evidence.

The actual existing `future_queue_snapshot.py` ran only on these local copies. Changes are limited to `operation_samples`, `operations` and queue/observation summary fields. Samples append 120→121; source results and tracking bytes are unchanged; hypotheses remain 3,375 S1 with no new/removal/promotion. Preservation verifies 3,992 candidate documents, 596 completed versions, 3,696 historical failure versions and 1,786 reviews. This is a local impact preview, **not Gate1 PASS**. UUID/time fields require a new transition on the actual approved generation.

## Scope of a later approved Gate run

Gate1 creates a dedicated storage fault/interleaving probe and publishes the operating candidate projection on `future-bottleneck-data`. Its source/judgment repair path is conditional; both prepared preservation checks currently pass. The Stage5 native-claim fault test uses a separate `ops/bct-native-claim-probe-*` branch. This is distinct from Gate5's true production publication.

Stage5 restores the **same existing selected** `Qwen/Qwen2.5-7B-Instruct-GGUF` revision `bb5d59e06d9551d752d08b292a50eb208b07ab1f` and llama.cpp `79e2e74eb11022c1ba2e438df7f0ca2d4c10f8b6`; GGUF hashes remain `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` and `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a`. Fresh setup builds/loads this runtime before resume checks, then permits up to **50 fresh readings**. This is not GLiNER substitution or a new model choice. The separate V4 consumer's enable variables are not changed by these Gates.

Gate5 can append actual source/access/review state and atomically publish `future-candidates.json`, `future-tracking.json`, both `.ui.json.gz` projections and content-addressed shards with nonforced CAS, immutable readback and idempotency checks. Existing source judgments/history, completions, TARGETs and predictions must pass preservation. A new Gate5 diff cannot be invented before its actual bounded reading receipts exist.

Existing limits remain: 100-minute standard public Ubuntu job; 300-second source receiver; 6GiB compressed/3GiB expanded/2GiB reserved source disk; 64MiB literal corpus copy; 5GiB per Qwen weight-part download; 120-second startup; 180-second inference requests; 30-minute reading deadline; 600-second native-claim child. Existing compile/download setup has no separate overall timeout or disk preflight; the job deadline still applies. No new cache, model framework, paid endpoint or runner is added.

## Preconditions and safe compensation

After explicit user approval, freeze the actual new main merge SHA and refresh the four heads/paired roots. Reuse unchanged exact evidence; if production advanced, prepare its read-only pair/impact again. Recheck all required artifact bindings and the recovery expiry. Keep main/data, HOLDOUT and frozen engine hashes unchanged.

There is **no automatic rollback after publication**. If a step fails, stop and preserve both before and returned publication commits/root hashes; inspect immutable published bytes first. A failed readback can follow a successful ref update. Any needed compensation must be a separately reviewed append-only merge at the exact current generation, retaining valid new readings/history and legitimate concurrent additions. Use nonforced CAS; reject an unexpected moved ref instead of blindly restoring the whole old snapshot. Do not reset/force/delete branches or overwrite canonical main/data.

Only an actual successful new-main run with every required Gate execution, exact SHA and unexpired artifact can support a later, separately approved `config/bct-operating-release.json` receipt-only PR. Its intentional guard exclusion avoids a circular code hash; every other covered code/test blob must match. This preparation changes no previous Gate verdict and claims no new Gates0–6 PASS, independent performance PASS or seven-day start.
