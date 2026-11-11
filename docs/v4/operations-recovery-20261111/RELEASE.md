# Operating release recovery — 2026-11-11

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`; existing plan `BCT-V4-Q-1.0`/Q2. Development baseline `42ee0a6...`, main baseline `28d0b8c648c0218ab2e74a1fa04ca8d63e659933`. P0 current-tree release remains **BLOCKED**. P2 has a concrete minimal main-based candidate, locally committed after parent review, ready for a draft PR. [RELEASE.json](RELEASE.json) contains exact hashes, scope and verification.

## Preserved real Gate evidence

Artifact `11783493914` from actual Gates 0–6 run `38331945733` was downloaded before its **2026-11-12 01:47:21 UTC** expiry. It is 45,073,105 bytes; SHA256 is exactly the recorded `00ac5d87109c6c365f9d2a19fe2f15a83919012ed012222f9b4932fd5d70243a`. All 3,313 ZIP members passed CRC checks; all content-addressed source/evidence files passed their hashes. The CLI redirect route returned403, while the supported connector download succeeded without credential changes.

The local ZIP is preserved at `/tmp/bct-operations-recovery-20261111/preserved/bct-recovery-checkpoint-38331945733.zip` and an equal Git-ignored workspace copy at `var/v4/operations-recovery-20261111/preserved/bct-recovery-checkpoint-38331945733.zip`. Raw/source files were not committed, uploaded or exposed in report text. These are local copies, not a new durable remote archive. The guard still needs an unexpired GitHub artifact binding; a local copy cannot substitute for that requirement.

Actual `verify_restored` passed for 19 root-file pins and the complete verified cache inventory: 1,677 source text files, 77 evidence text files, 1,467 evidence native files, 8 source HTML files and 51 native-claim files. The inventory SHA256 is `61254209fc5697fdd3e2789806214ee15cd01d564386ce75eb4bc7acdda2ed5a`. Historical Gate results are preserved for their original code. Its checkpoint still explicitly says FULL clean status is blocked pending operating publication stage 7/FULL; it is not recast as overall pipeline completion.

## Concrete minimal candidate

Isolated worktree: `/tmp/bct-operations-recovery-20261111/main-candidate`. Commit **`018f5bb1aa9d27e2891b9902155cb14107f9b019`**, parent exact main `28d0b8c6...`, tree **`5ec9d9b63e6873d4406a7ad0e1633bcb067d5310`**. It changes 14 files, 759 insertions/21 deletions.

The candidate transfers only applicable narrow fixes from `09cbdf2`: source-bound named order equipment, incomplete TARGET/event diagnostics, bounded REVIEW artifact transport, and truthful RSS AI outcome/publication verification. It includes the two independently verified official DOE feed URLs. Tests remain focused on these behaviors. No V4 package or development documentation/source DB is merged into main; quantitative Q3 diagnostics and the V4-only historical test repair remain on development.

A real restore prerequisite defect is also repaired: main's default recovery request still pointed to `37956471056` with no pinned root-file hashes or cache inventory, although the existing workflow rejects exactly those omissions. The new request cites the authenticated `38331945733` artifact, its 19 real root hashes and full inventory. Its bytes have SHA256 `b1f169d77cec98e2a6e4447a38c372700161eff7aeddcbcbf72ee5dadef2e90f`. A response/restore-contract test first failed for the stale run ID, then passed with the repaired manifest. The manifest grants no operational permission and changes no Gate success condition.

The release guard, operating release receipt, CPU consumer workflow/pin and all four frozen discovery engines are byte-identical to main. Replay of the candidate against stored real historical release metadata still refuses with `validated code/test file set changed or missing`. There is no workflow exclusion, invented release receipt or main change. PR text is prepared at `/tmp/bct-operations-recovery-20261111/MAIN_PR_BODY.md`; remote branch push/PR creation belongs to the parent task. The PR must remain draft until the actual release prerequisites and user approval are satisfied.

## What the actual Gate workflow would do

| Step | Actual effects and remaining condition |
|---|---|
| Gate 0 | Reads four branch snapshots, canonical SQLite integrity and preserved identities. Its combined entrypoint proceeds into Gate 1 writes. |
| Gate 1 | Creates a dedicated remote fault/interleaving probe branch; can repair production preservation state; publishes bundle/queue projection on `future-bottleneck-data`. Current operating impact preview is required first. |
| Gate 2 | Performs actual DNS/HTTP for selected failed and official sources; writes local cache/report. Repeated known failures need a changed condition or legitimate exact-receipt reuse. |
| Gate 3 | Restores exact source observations and inventory. Technical errors become retryable when the overall code SHA changes, which needs scope review before a run containing unrelated source changes. |
| Gate 4 | Captures the 74 preserved missing-evidence source versions and performs any scope-ready bounded external search. It does not create review completions or promotions. |
| Stage 5 pilot | Unconditionally builds/loads pinned llama.cpp/Qwen2.5-7B GGUF before examining resume state. A qualified resumed run drains unread sources, up to 50 new calls; native worker claims can also occur. |
| Gate 5 | Atomically publishes candidate/tracking roots and display projections, including source/access/reading-state changes, with immutable readback and idempotency checks. |
| Gate 6 | Requires real preceding gate/source receipts plus Python/JS/lint/syntax/type/build and fixed230 QA. Local quality tests alone do not satisfy it. |

The Stage 5 Qwen runtime is separate from the GLiNER V4 CPU consumer runtime. Preserved old Qwen inference receipts are not an available executable runtime or permission to run more inference. Under this task's CPU/model-zero boundary, the existing full workflow cannot be dispatched unchanged. No Gate script, Gate condition or reader fallback was modified to manufacture a PASS.

Before any Gate 1/5 operating mutation, pin both authoritative roots at one immutable generation, prepare the proposed diff on copies, enumerate affected IDs/fields/source versions/reviews, verify unchanged TARGET/prediction/source judgments, and review recovery. Any compensating publication must use non-forced CAS and retain legitimate concurrent additions/history; blindly restoring an old whole snapshot is unsafe. The current production diff has not been computed and no operating mutation was performed.

## Fixed230 source dependency

Original source run `37790294699` no longer lists an artifact. The preserved Gate ZIP contains the historical fixed230 report, but no original `documents/`/`raw/` corpus. Body-only caches cannot recreate immutable document/native metadata. Required input fingerprint remains `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec` for exactly 230 original provenance-PASS document ID/body/native hash triples.

The parallel bounded REVIEW Actions check is being extended to inspect historical document metadata inside its one existing ZIP download, with independent caps and exact fingerprint matching before any raw-byte hash reads. It does not extract/upload the historical corpus or count its discovery as Gates 0–6 completion. Actual intact-copy verification is pending that run; missing source QA remains blocked.

## Verification and next action

Clean main baseline: **942 passed, 1 existing holdout skip**. Five extraction/graph regressions failed before transfer. Candidate executable changes: **1000 passed, 1 existing holdout skip** in 24.22s; **34 JavaScript tests**, **70 focused tests**, and **3 preserved real-source checks** passed. The real-source checks read the existing development DB without copying it into the candidate and verified imports from the candidate tree.

Ruff F checks, compileall, the existing 47-file recovery mypy scope and wheel build passed. After the configuration/feed-only follow-up, **19 recovery/guard/RSS tests passed** in 0.77s. The stale manifest test failed first. Diff checks passed. Quality tools were installed only into an isolated `/tmp` dependency directory; no model package/runtime was installed.

No new current-tree Gates 0–6 PASS, actual model call, external AI request, paid endpoint, operating write, main mutation or push is claimed. One isolated local candidate commit was created with parent authorization. Next actions are the parent draft PR and bounded source/runtime/impact evidence; actual release receipt and main merge remain separate approval/application steps after valid evidence exists.
