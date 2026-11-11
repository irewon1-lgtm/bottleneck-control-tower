# Actual Pages delivery and dashboard freshness — 2026-11-11

Evidence only for `BCT_V4_OPERATIONS_RECOVERY_20261111`. This audit changes no UI, export code, workflow, main configuration or `PROGRESS.json`. Full structured receipt: [DASHBOARD_RECOVERY.json](DASHBOARD_RECOVERY.json).

## Current published result

[Live Pages](https://irewon1-lgtm.github.io/bottleneck-control-tower/) now publishes development commit **`2e86fd82edb1eeb3fb21c1afb8add7da6b890e98`**, through the approved main workflow at **`e31743a91ab3604421ec7c35796dfda8f63dd51f`**. The main workflow commit and exported development commit are different, expected identities.

| Actual check | Evidence |
|---|---|
| Development CI | [43000796112](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43000796112), SUCCESS; actual job log: **1,870 Python passed / one skipped**, **34 JavaScript passed / zero failed** |
| Dashboard release gate | [43000796038](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43000796038), `verify` SUCCESS; separate dispatch-only `readonly-release-revalidation` job correctly skipped |
| Pages publication | [43001061701](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43001061701), build SUCCESS and deploy SUCCESS; deployment completed **10:09:40 UTC** |
| Actual deployment URL | Deploy job log explicitly reports `https://irewon1-lgtm.github.io/bottleneck-control-tower/` |
| [Live manifest](https://irewon1-lgtm.github.io/bottleneck-control-tower/build-manifest.json) | Code `2e86fd82…`; generated **2026-11-11 10:08:34.745292 UTC**; 1,703 evidence details |
| [Live dashboard JSON](https://irewon1-lgtm.github.io/bottleneck-control-tower/api/dashboard.json) | SHA256 **`257631ee907c2ec1761f9acb872fe6f95511c1494fef2d479a1f7d93ca99773a`**, exactly matching the manifest |
| [Full published progress JSON](https://irewon1-lgtm.github.io/bottleneck-control-tower/api/progress.json) | Parsed content exactly equals `PROGRESS.json` at `2e86fd82…`; actual PR44 receipt is **`PR44_EXPLICITLY_USER_APPROVED_AND_MERGED_NORMAL_MERGE`** |

The previous checked baseline was `fbbc4d0a…`, generated 09:29:17 UTC and deployed by [42995542252](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42995542252). Its older approval-pending progress receipt has been replaced by the verified `2e86fd82…` receipt.

## Code delivery is current; research data remains historical

The actual manifest and dashboard still record **`data_at = 2026-10-14T23:16:13.592709+00:00`**. This remains **BLOCKED for current research-data freshness**. The new publication does not query current canonical acquisition or the private monthly facts database when a user refreshes the page.

The existing automation cards retain their original research scope: 15 manual research collection runs, last collection October 14 15:15 UTC, last CPU research record October 14 23:16 UTC, historical API reader `DISABLED`, and historical Shadow `NOT_ACTIVATED`. These fields do not describe the current Actions run counts, current CPU enable variable or current background execution. Existing historical rows and the original data timestamp were preserved.

The dashboard still exposes 511 main research evidence rows plus CPU/reported details, totaling 1,703 exported details. Its strict future-candidate counts remain S1/S2/S3 **0/0/0**. A current code/approval receipt does not turn these historical source records into new research results.

## Public Actions metadata, with explicit windows

The read-only public Actions REST query used a fixed `created` range from **November 4 00:00:00 UTC through November 11 10:09:58 UTC** and returned **299 unique runs** across all branches and workflow types. This calendar window lasts **seven days, ten hours, nine minutes and 58 seconds**; it is not a strict seven-day denominator.

The strict seven-day column below is filtered from that same captured metadata: **November 4 10:09:58 UTC through November 11 10:09:58 UTC**. Counts concern main automatic/scheduled/workflow-run executions. Manual recovery dispatches are separated.

| Workflow | Calendar window | Strict seven-day window |
|---|---|---|
| RSS collection | 44: 43 success, one failure | 42: 41 success, one failure |
| Precursor acquisition | 44: 41 success, one failure, one cancelled, one skipped | 42: 40 success, one cancelled, one skipped |
| REVIEW intake | 44: 43 success, one failure | 42: 41 success, one failure |
| CPU automatic consumer | 44, all skipped | 42, all skipped |
| RSS AI annotation workflow | 15 success | 14 success |
| Evaluation observer | 14 success | 14 success |
| Future body candidates | 59: 58 failure, one skipped | 56: 55 failure, one skipped |

Two successful manual CPU-consumer recovery dispatches are excluded from both automatic CPU columns. They are not new scheduled CPU readings. Workflow success is not semantic extraction success; skipped CPU runs do not by themselves identify which guard blocked execution. Metadata does not supply source/body row counts or semantic HOLD totals, so those current counts remain **UNKNOWN from this source**. Zero alerts cannot be substituted for zero HOLD records.

The latest RSS inside this fixed snapshot is [42990958603](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990958603), created **08:56:05 UTC**, followed by successful precursor [42991420695](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42991420695) and REVIEW [42995175538](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42995175538). No later scheduled chain is inferred from a cron time or the current clock. Subsequent monitoring uses its own later receipt/window.

## Smallest existing-format assessment

The existing full-progress link already publishes the actual approved recovery receipts without a UI change. Root updated that ledger, and the existing verification/publication chain delivered it successfully.

Replacing historical `automation.runs` fields with Actions execution counts would mix source/body-attempt denominators with workflow-run denominators. The current card text also explicitly describes manual research. Therefore an export-only replacement cannot accurately represent current operating health with the current hardcoded text.

If separately authorized later, the narrow extension would be an explicitly dated, allowlisted **`PUBLIC_ACTIONS_METADATA_SNAPSHOT_WITH_EXPLICIT_SCOPE`** projection and a small optional data binding in the same existing three automation cards. It would preserve the historical rows and `data_at`, use public run/status/time/count fields, and use actual structured processing receipts for source rows, CPU windows or HOLD totals. No raw logs, source bodies, private artifacts, private repository content or secret values would be exported. The necessary existing files would be `tools/v4_dashboard_static_export.py`, `src/bct/v4/dashboard_web/app.js`, `.github/workflows/ui-pages.yml`, and a small read-only metadata helper.

That extension is **deferred**. No new health refresh contract, trigger, UI, infrastructure or export feature was implemented here. Current publication/approval freshness is verified; current research-data freshness remains BLOCKED.
