# Latest private database restoration — 2026-11-11

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`; fixed plan `BCT-V4-Q-1.0`. This resumes the previous audit's exact blocker through the existing approved Actions context. No local secret retrieval, new key, replacement database, source reread, CPU/model execution or remote state write is involved. The historical audit remains unchanged.

## Actual current-generation restoration

The existing development workflow `v4-cpu-private-research.yml`, purpose `official-state-read`, was inspected before dispatch: only its dev read job runs; public permissions are `contents:read/actions:read`; checkout does not persist credentials. Its existing private-reader token and state passphrase are passed only to the approved reader step. No publication, model, source acquisition or cache upload step runs.

Dispatch returned **HTTP 204**, accepted permission `actions=write`. [Run 42988130440](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988130440), job `130414143686`, completed successfully on development SHA `42ee0a6ee6b0ed21228a0409aa64e973359bf65f`. Every other job, including research and publishers, was skipped. The run took approximately 75 seconds end to end.

| Actual restored state | Result |
|---|---|
| Monthly tag / generation | `bct-v4-archive-monthly-2026-10` / **6**, `PAGE_DELTA` |
| Manifest SHA256 | `f939433f6366438abb64b6a4c89f8305b6b91727ecce4362384c03b6e6a908fe` |
| Previous manifest SHA256 | `1da6747b431087f1f31bdc82537ad1cc0306ff7de7c663bdacee59afebd5921e` |
| SQLite SHA256 | `06bef86b0667c7d7170dc1521c7646324824edd76085eb61c1cb7913381e2093` |
| Restored tables | **8**, exact hashes and integrity validated; **60,071 events**, two metadata rows; other six tables empty as required by the facts-only schema |
| Quantitative facts | **42,601 observation versions; 38,046 numeric / 21,916 physical numeric observations** |
| Official fact versions | **14,690** |
| Signed contract records | **486**, after exact contract/award deduplication |
| Selection-repair packet | Exact stored packet hash `2eae3a7099613bdb94868e2ba050ddbc7d6d35e2098ab8407b4508ef2b928eb0` confirmed |
| Monthly assets | **14 / 38,084,522 bytes**; remaining monthly budget 230,350,934 bytes / 386 slots |
| Strict independent pairs / S2 / S3 | **0 / 0 / 0** |
| Source HTTP / remote writes / AI calls / CPU windows | **0 / 0 / 0 / 0** |

The existing archive restore validates authenticated decryption, base/delta ciphertext and plaintext hashes, every page transition, final SQLite hash, all eight table hashes, integrity and the facts-only rights/schema audit. Original source bodies and native files are deliberately absent. This proves the latest saved research-facts capsule is recoverable; it does not restore the historical original-source corpus or prove independent forecast performance.

The prior audit's “passphrase absent from the local process” limitation is now resolved **for this actual restore** by using its existing secret-enabled Actions job. No secret was copied into this workspace or recreated.

## Additional restart and previous-generation proof

The existing reader lacked an actual separate-interpreter restart and an explicit immediately prior-generation history comparison. A minimal proof-only extension adds `official_restore_audit` as a second separately bounded 120-second command in the same read job. It:

- Reopens the actual downloaded checkpoint in a new Python process, with the private token, passphrase and GitHub token environment variables removed from the child.
- Rechecks its exact SQLite hash, all eight table hashes, integrity and facts-only schema through the existing typed restore.
- Restores the immediately previous generation through the existing authenticated archive reader, verifies the parent-manifest link, and compares exact metadata and ordered prior event rows against the new-process current database.
- Checks that the remote head and asset inventory remain unchanged and refuses existing output directories, stale inputs, corrupt prior generations or a downgrade to the old Git state.

**The extended proof passed in actual Actions**, [run 42989791426](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989791426), job `130419573071`, on exact reviewed development SHA `ab2cc04a13af13903fe980e2532a073f2a4ad7aa`. Its current-state reader took **72 seconds** and its separately bounded restart/history proof took **62 seconds**; both stayed below their own 120-second limits. All publisher/research jobs were skipped.

The new Python process (PID 2262, with account credentials removed) restored generation 6 with the same SQLite hash and all eight tables. Generation **5** also restored successfully, SQLite SHA256 `6b43a0dcc5c3ecd0de2a981540835498d5e532fc4dd8a369ce2ef25ed8c72e46`; its manifest hash equals generation 6's recorded parent. Exact comparison preserved **all 60,049 previous events and metadata** in the **60,071 current events**. The full base plus both page deltas have validated ciphertext/plaintext hashes recorded in the JSON evidence. The run verified unchanged remote head/asset inventory, and an independent post-run API inventory still matched all 14 original assets exactly.

Four new fixture tests passed; 28 related archive, monthly, private-state and workflow tests passed. No storage stress or model work was run. One initial corrupt-prior fixture failed because its unpinned wall clock selected a full checkpoint; pinning that fixture's simulated publication time exposed the intended delta corruption and all four cases then passed. This was a fixture timing correction, not a relaxation of production checks.

Commands:

```bash
gh api --method POST repos/irewon1-lgtm/bottleneck-control-tower/actions/workflows/v4-cpu-private-research.yml/dispatches --input /tmp/bct-official-state-read-dispatch.json
.venv/bin/python -m pytest -q tests/test_v4_restore_audit.py
.venv/bin/python -m pytest -q tests/test_v4_monthly_storage.py tests/test_v4_release_archive.py tests/test_v4_quantitative_private.py tests/test_v4_cpu_research_workflow.py
```

Each dispatch input was only `ref=codex/bct-v4-integration`, `purpose=official-state-read`: one baseline execution and one execution after the reviewed proof extension. Compact nonsecret job receipts and exact results are stored in [DB_RESTORE.json](DB_RESTORE.json). No unchanged failure was retried. Main `28d0b8c6`, CPU pin/enable settings, schedules, private refs and all original data are preserved by this work. Q1/Q2 remain PARTIAL; independent Q3 pairs and LIVE firsts remain zero.
