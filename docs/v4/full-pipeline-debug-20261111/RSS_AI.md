# RSS AI execution and persistence audit — 2026-11-11

Task: `BCT_V4_FULL_PIPELINE_DEBUG_20261111`. Existing plan: `BCT-V4-Q-1.0`; Q1/Q2 remain PARTIAL, Q3 eligible independent pairs remain 0. Objective Lock, existing AI FAIL/independent evaluation BLOCKED, historical performance and S gates remain unchanged.

The observed RSS AI throughput is **0 annotations and 0 persisted AI batches**, despite 15 successful GitHub workflow runs from 2026-11-04T02:26:44Z through 2026-11-11T01:58:59Z. For all 15 runs, the configuration step succeeded while annotation and publication both had `skipped` conclusions. Under the unchanged configuration guard this is `SKIPPED_CONFIG`: the existing `OPENAI_API_KEY` was absent/empty. No Secret value was retrieved. The latest example is [run 42942786702](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42942786702), whose annotation and publication steps were skipped at 2026-11-11T02:00:36Z.

The workflow, annotation module and their existing tests had identical Git blobs on development `23a0615f` and main `28d0b8c6`. This is existing behavior shared by both branches. The successful workflow conclusion measured a completed configuration check; it did not demonstrate annotation, new input consumption or saved results. No saved RSS AI output from those 15 skipped runs exists to verify.

The local repair adds an always-run, secret-free outcome report and JSON artifact. It preserves the existing key guard, schedules, shared RSS write lock, batch limit, terminal article error rows, versioned deduplication and publication conflict check. It does not call a provider or configure a key. The receipt uses these outcomes:

| Outcome | Required evidence | Job result |
| --- | --- | --- |
| `ANALYSIS_PASS` | At least one valid annotation, no article errors, successful publication and verified saved snapshot restore | Success |
| `NO_NEW_INPUT` | Annotation batch ran and returned processed/success/error all 0 | Success, explicitly zero throughput |
| `SKIPPED_CONFIG` | Existing configuration check reports absent/empty key | Success, explicitly skipped |
| `FAIL_RUNTIME` | Restore/configuration/batch failure, invalid counters or terminal article errors | Failure |
| `FAIL_SAVE` | A nonempty batch lacks successful publication/verification | Failure |

Article errors still save their terminal `ERROR` rows before the final report fails the job. The receipt reports valid results and persisted rows separately. After pushing a saved batch, publication now verifies the remote data ref matches the saved commit, fetches that immutable commit, and loads its snapshot through the existing hash/SQLite integrity validator in a new Python process. A conflict or failed verification cannot produce `ANALYSIS_PASS`.

Offline verification completed with **35 passed, 0 failed, 0 skipped**. This includes the actual missing-key configuration shell, success/no-input/runtime/save classifications, redaction, existing 25-item batch save/restore/resume and non-AI table preservation, and the publication shell against a disposable local Git origin. That Git test queries the restored `OK` annotation row; a separate concurrent-writer case verifies refusal without replacing the remote ref. Baseline RSS AI tests were 10 PASS. New outcome tests and workflow receipt wiring were observed failing before implementation.

```sh
.venv/bin/python -m pytest tests/test_rss_ai.py tests/test_rss_ai_workflow.py tests/test_rss_ai_outcome.py tests/test_rss_state_workflow.py tests/test_rss_cycle_families.py tests/test_rss_collector.py -q
```

Machine evidence, per-run step results, immutable baseline blob IDs and offline receipt examples are in [RSS_AI_EVIDENCE.json](RSS_AI_EVIDENCE.json). The local tests establish reporting and persistence behavior. Live provider analysis remains unexecuted, and no deployed correction or real analysis PASS is claimed. Provider calls, paid API cost, key/provider setup, new Actions dispatches and production data/cursor changes in this task are all 0. With the existing key absent, the correct future result remains `SKIPPED_CONFIG`; a green workflow alone must not be counted as AI throughput.

The existing historical preservation test initially failed because it checked the evolving current RSS AI and review workflow paths against sealed pre-repair hashes. The authorized current workflow repair follows the test's existing evolved-assets pattern: exact original workflow bytes from `23a0615f` are preserved in `docs/v4/dashboard/frozen-assets/rss-ai.yml` and `review-lead-shadow.yml`. Their SHA-256 values remain `fbac7572cc22a079718c11df6494bd9452bf5db6b92cbe282a261e63ba73ef27` and `651fb347b99e07f9b2aae13b964e792324dfaf4d0a856b678c7b4e63bdc0f403`. The golden `initial-scope.json` manifest and its expected hashes were not changed. Historical bytes are still checked, and current workflows are exercised by RSS AI/review artifact tests. Follow-up preservation, RSS AI and review artifact checks passed together; counts are recorded in the machine evidence.
