# Collector connection follow-up — 2026-11-11

Task `BCT_V4_FULL_PIPELINE_DEBUG_20261111`, existing plan `BCT-V4-Q-1.0`/Q2. Evidence: [COLLECTOR_CONNECTIONS.json](COLLECTOR_CONNECTIONS.json). This is a connection/schedule audit, not source refresh or a second progress ledger.

The latest preserved RSS receipt has 111 successful feeds and 14 failed: seven ESA404, six DOE network/TLS failures, one USGS empty feed. No unchanged failed feed URL was requested again.

The supplied official ESA directory `https://www.esa.int/rss` returned **HTTP404** on its single GET (1.33s). It provided no verified replacement link. Category-preserving feed replacements and real replacement XML entries remain **UNKNOWN**. `rss_feeds.yaml` is unchanged; no guessed URL was introduced. DOE/USGS failures remain isolated and were not retried without changed evidence.

At 2026-11-11 07:43:31 UTC, one GET per existing unkeyed metadata landing page returned200:

| Source | Official URL | Seconds | Bytes |
|---|---|---:|---:|
| M3 | https://www.census.gov/manufacturing/m3/index.html | 0.434 | 502449 |
| G17 | https://www.federalreserve.gov/releases/g17/ | 0.186 | 331230 |
| EIA860M | https://www.eia.gov/electricity/data/eia860m/index.php | 0.206 | 93612 |

Hashes and Last-Modified headers are in the JSON. These three checks disabled redirects/retries and saved no raw response file. They establish metadata connectivity only: no numeric file download, API collection, revision ingestion, DB write, numerical validation or Q1 completion occurred. Reported local SEC/Census/EIA credential absence was respected; no keyed request, known403 retry or credential value output.

No real scheduled Q1/Q2 process was found in the current development workflow definitions or exact main `28d0b8c6...` CPU workflow. In `.github/workflows/v4-cpu-private-research.yml`, Q1/Q2's prior job (line389) requires `workflow_dispatch` **and** the integration ref; processing/publishing depend on that job. The main workflow contains only legacy pinned CPU research/publish and seed/recovery/bridge dispatch purposes, not the newer quantitative jobs. Its acquisition `workflow_run` trigger does not execute `tools/v4_quantitative_batch.py`.

The registry's M3/G17/EIA policies (lines5880/5903/5926) explicitly state `MANUAL_FIXED_SCOPE_ONLY; dataset-native new dates/revisions; no new schedule`; registry `schedule_enabled=false` is consistent with the workflow audit. Manual successful research batches and working public landing pages do not establish recurring Q1/Q2 operation.

Four new official public GETs total; failed-feed retries0, new models/AI/keyed API/data download/DB writes/operational changes0. This follow-up changes evidence only. Next dependency: obtain a verified official category-preserving ESA directory/feed mapping; keep quantitative operation manual until a separately authorized reviewed schedule and its real end-to-end persistence evidence exist.
