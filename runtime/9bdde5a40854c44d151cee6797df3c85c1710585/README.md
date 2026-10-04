# BOTTLENECK CONTROL TOWER — Stages 0–3

## Independent RSS AI annotation

`.github/workflows/rss-ai.yml` runs at 07:20 / 19:20 KST (GitHub scheduling can
be delayed), or via workflow_dispatch. Set repository secret `OPENAI_API_KEY`;
the optional repository variable `RSS_AI_MODEL` defaults to `gpt-5-mini`.
It restores the verified existing data-branch SQLite snapshot, runs the existing
review logic, and persists only AI annotations with the existing snapshot helper.
It shares the RSS database concurrency lock and refuses stale writes. Missing
secrets or invalid snapshots stop only this workflow; no new database is created.
Article ERRORs are saved normally. An empty batch does not commit. Logs contain
only processing counts, never provider errors or article/AI response text.

`python -m bct.rss_ai --config config.yaml --feeds rss_feeds.yaml --model YOUR_MODEL --limit 3`
requires `OPENAI_API_KEY` in the environment. It is never run by RSS collection.
Run it separately against the existing SQLite snapshot. At most
20 unreviewed active RSS articles with existing signals are sent, using only the
title, snippet and signal names. One retry is allowed; a second failure records
a terminal `ERROR`. Both `OK` and `ERROR` are skipped until the model or
`--prompt-version` changes. The script creates one
`rss_ai_reviews` table alongside the existing tables; it does not change Core,
SIGNAL, WATCH/PROMOTE or the `radar_items` rows. Its annotations are advisory,
and `UPSTREAM_SOURCE` can be used to identify reprints in a future review; the
existing candidate counts are not changed by AI.

## Media Cloud RADAR intake

Media Cloud is the primary metadata feed for this pilot; GDELT remains an
optional adapter. Create a Media Cloud API key and supply it via
`MEDIACLOUD_API_KEY` (never commit it to YAML or a report):

```sh
export MEDIACLOUD_API_KEY='your-key'
python -m bct.collectors.media_cloud.cli --config config.yaml --query shortage --limit 5 --run-key pilot-1
```

The default runs three separate searches: `shortage`, `"lead time"`, and
`"capacity constrained"`. Each searches a two-day UTC date window in Media
Cloud's US National Collection, first page only, requesting 5–20 stories.
Successful results store Media Cloud story ID, publisher, title, URL and its
estimated publish date in the existing `radar_items` table. The source does
not expose a downloadable article excerpt through the search API, so `snippet`
is NULL. An API key is required. No article body is stored. Each query has an
independent `collector_runs` key; failed keys can be retried, while a fresh key
checks the same query for duplicates or metadata changes. Requests are serial
and spaced 31 seconds apart when a key is present because some endpoints are
limited to two requests per minute. Existing Research Core and schema are
unchanged. See `MEDIA_CLOUD_RADAR_REPORT.md` for verified outcomes.

## Discovery RADAR intake

For a serial pass over the configured 29 RSS feeds followed by an automatic
PRESSURE/RELIEF and contextual family rebuild, run:

```bash
python -m bct.rss_cycle --config config.example.yaml --feeds rss_feeds.yaml --limit 10
```

Run the command again whenever another feed snapshot is needed. The RSS
Collector retains prior articles, deduplicates by source and article URL, and
records failures per feed; the derived family report is in
`var/derived/rss_candidate_families.json`. This command does not schedule itself.
`promote` is only a two-source, two-article PRESSURE review gate, not a verified
bottleneck claim.
For manually reviewed families, the same output also shows `core_status`,
`confirmed_scope`, `unresolved_scope` and `re_review_required`. Manual judgments
and vetted material changes use `radar_family.review` and
`radar_family.material_change` records in the existing audit log. An unchanged
RSS article or a conditional/reprinted claim never opens a new review. A new
article requires manual verification of a current original observation before
`record_material_change` can raise a review trigger.

`bct-radar` reads one free broad source, the GDELT DOC Article List API. Five
small queries cover shortage, lead time, capacity constrained, qualification
delay, and unable to meet demand across industries. It collects metadata leads only; RADAR entries are not
research evidence or verified bottlenecks.

```sh
python -m bct.collectors.radar.cli --config config.yaml --run-key 2026-09-29T12:00Z --limit 10
```

Use a **new run key** to refresh the feed; the same successful key is a no-op,
while a failed key can be retried. Each query gets its own collector run and a
timeout does not stop the other queries. Use repeated `--query` options to
select a subset; by default all five run. The default key is a UTC timestamp. Each
query is limited to the newest 24 hours and one page of at most 25 results. It does
not guarantee complete news coverage. Each URL is hashed for identity, so a
changed headline updates the same row and records old/new values in `audit_log`.
An article URL change may produce another row. GDELT Article List does not
provide a reliable original publication timestamp or article excerpt: both
`published_at` and `snippet` remain NULL unless a future provider supplies
them. `collected_at` records the first ingestion time. `source` is the publisher
domain and `source_type` is `NEWS`. Article bodies and search JSON are not
written to RAW. Backup and restore include RADAR rows through the existing
SQLite snapshot. The `0013_radar_items` migration adds the table and its
hard-delete guard without changing the Collector run lifecycle or Research Core.

The endpoint and query syntax follow [GDELT's DOC API documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).

Stage 0 supplies storage and recovery. Stage 1 adds one SEC Collector for the most recent exact forms 10-K, 10-Q and 8-K. Stage 2 adds one USAspending contract award Collector. Stage 3 adds one Federal Register keyword search Collector. All three use `SourceRecord`, `ingest`, and the shared `execute_run` lifecycle for run status and failure recovery. The attached `US3700_ANALYSIS.csv` is not imported or bundled. No AI, claim extraction, news, stress test, bulk ingestion or web UI is included.

## Federal Register Stage 3

Initialize once using the setup below. Search the newest documents for one keyword, first page only (default 3, maximum 100):

```sh
python -m bct.collectors.federal_register.cli --config config.yaml --keyword 'semiconductor' --run-key 2026-09-29 --limit 3
```

The request uses the [Federal Register public API](https://www.federalregister.gov/developers/documentation/api/v1) `/api/v1/documents.json` with `conditions[term]`, `order=newest`, and `per_page`. The original JSON response bytes are preserved in RAW. `federal_register_documents` stores document number, title, type, publication date, issuing agency names, HTML URL and a foreign key to the RAW response. Document number is the unique source identity. Later changes to those fields update the same canonical row with an audit entry and a pointer to the new response; the prior RAW remains immutable. Repeated unchanged results are counted as duplicates.

This is a search-result metadata collector, not a downloader of full document text, PDFs or past pages. FederalRegister.gov [states](https://www.federalregister.gov/developers/documentation/api/v1) that its displayed renditions are not the official legal edition; verify legal conclusions against the official publication. `STAGE3_REPORT.md` records the live sample and tests.

Requests are serial, have a 25-second timeout and 4 MB response limit, and are not automatically retried. A completed run key is a no-op; use a new key to check again. A failed/interrupted run key can be explicitly retried. Do not use the same key in simultaneous workers.

## USAspending Stage 2

Initialize once using the setup below. Search by recipient text or by keyword, with one page of at most 100 contract awards (default 3):

```sh
python -m bct.collectors.usaspending.cli --config config.yaml --company 'LOCKHEED MARTIN' --run-key 2026-09-29 --limit 3
python -m bct.collectors.usaspending.cli --config config.yaml --keyword 'semiconductor' --run-key 2026-09-29 --limit 3
```

The API request uses [USAspending's Spending by Award POST endpoint](https://api.usaspending.gov/docs/intro-tutorial), limited to contract type codes A–D. Recipient search is a **search result**, not confirmed legal-entity matching. Results are limited to page 1, sorted by Award Amount; they are not a complete history for a company. The raw HTTP response is preserved byte for byte, named by SHA-256 in the raw store. `contract_awards` stores the provider's `generated_internal_id` as the external identity, public Award ID, recipient name, amount, agency, modification time, and pointer to the raw response. A changed award value updates the same canonical row, changes its raw pointer, and emits an audit event; the old raw response remains immutable. Identical results are counted as duplicates. `STAGE2_REPORT.md` records the live sample and tests.

Requests are serial, one page each, with a 30-second timeout and 4 MB response limit. There is no silent retry. A failed or interrupted run key can be resumed explicitly; completed keys do nothing on replay. Use a **new run key** for a later fresh search. Do not run two workers simultaneously with the same key.

## SEC Stage 1

First initialize the database using the setup below. SEC requests must have an identifying User-Agent with **your own reachable contact**. One run fetches the company submissions JSON and at most one primary filing HTML document per requested form (change with `--max-per-form`).

```sh
export BCT_SEC_USER_AGENT='Your Project your-real-contact@example.com'
python -m bct.collectors.sec.cli --config config.yaml --cik 320193 --run-key 2026-09-29 --max-per-form 1
```

The exit code is nonzero on failure and the JSON result includes `saved`, `duplicates`, `failed`, and `error`. A completed `run_key` is a no-op when invoked again; use a new key for a new daily scan. A failed or interrupted key can be invoked again. New filings are committed individually; previously saved filings are skipped by accession number, with no second document download. Runs and the error reason are stored in `collector_runs`.

SEC data locations follow the [Submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and [EDGAR archive layout](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). Requests are serial, spaced at least 0.25 seconds apart, limited to 20 MB per response, and do not retry automatically. SEC's [fair access guidance](https://www.sec.gov/about/developer-resources) currently limits total automated access to 10 requests per second; other processes using the same IP must also be counted. This prototype deliberately scans only `filings.recent` and exact form labels, not historical pagination, amended forms or all 3,700 companies.

Each successful filing creates one `documents` row referring to the immutable SHA-256 raw file. The original submissions JSON is also stored in RAW (`sec.submissions`) to preserve selection provenance. Content-addressed files can be shared by multiple records if identical. The submitted SEC HTML is preserved as received; no extraction is performed. `STAGE1_REPORT.md` records the live sample and tests.

## Setup

Python 3.10+ is required. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
cp config.example.yaml config.yaml
python -m bct.cli --config config.yaml init
python -m pytest -q
python -m bct.cli --config config.yaml health --deep
python -m bct.cli --config config.yaml backup
```

`storage_root` is resolved relative to the configuration file. `var/` is excluded from Git. The example creates `var/canonical/canonical.sqlite3`, `var/raw/sha256/`, `var/staging/`, `var/derived/`, and `var/backups/`. Runtime contents must be backed up separately from the Git repository.

Restore into a **new, nonexistent directory** so the live database cannot be overwritten:

```sh
python -m bct.cli --config config.yaml restore var/backups/backup-YYYYMMDDTHHMMSSffffffZ --to ./recovered-var
```

After restore, point a separate config at `./recovered-var` and run `health --deep`. `rebuild-derived` regenerates the disposable `raw_index.json` from canonical records.

## Source tree

```text
bottleneck-control-tower/
  pyproject.toml             dependencies and bct command
  config.example.yaml        validated YAML configuration
  alembic.ini                migration configuration
  migrations/
    env.py
    script.py.mako
    versions/0001_foundation.py
    versions/0002_documents.py
    versions/0003_contract_awards.py
    versions/0004_federal_register_documents.py
  src/bct/
    collectors/sec/          SEC-only transport, parser, runner and CLI
    collectors/usaspending/  USAspending-only search adapter and CLI
    collectors/federal_register/  Federal Register-only adapter and CLI
    config.py                paths and config validation
    db.py                    SQLAlchemy sessions and Alembic upgrade
    models.py                canonical schema
    collector.py             future Collector Protocol and SourceRecord
    core.py                  ingest, runs, jobs, entities, freezes, audit
    backup.py                online SQLite snapshot and raw-file restore
    health.py                database/raw checks and derived rebuild
    cli.py                   init, migrate, health, backup, restore
  tests/
    conftest.py              isolated SQLite fixture
    test_foundation.py       failure and recovery scenarios
    test_sec_collector.py    SEC integration using deterministic fake responses
    test_usaspending_collector.py  contract collection and recovery tests
    test_federal_register_collector.py  document collection and recovery tests
```

## Data contract

| Area | Contract |
| --- | --- |
| Raw | `SourceRecord` bytes pass staging, SHA-256 and atomic hard-link publication. Blob path is `raw/sha256/<first-two>/<digest>`; blobs are never overwritten. `raw_documents` stores path, hash, source and external ID, not a BLOB. Same source, external ID and hash produces one record; changed content creates another version. |
| Canonical | SQLAlchemy models are modified through `core.py`. UUID primary keys remain stable when names change. Entities use `status` and `deleted_at`; restoring keeps the same ID. Every service mutation writes an audit event in its DB transaction. |
| Derived | `derived/raw_index.json` is a disposable demonstration output. Delete it and run `rebuild-derived` to regenerate it from canonical raw records. Future projections must follow the same rule. |
| Collector | A future adapter implements `name` and `collect(checkpoint) -> Iterable[SourceRecord]`. This Stage supplies no vendor-specific adapter or scheduler. Core accepts bytes and IDs; the adapter owns fetching, pagination and checkpoint semantics. |
| Runs/jobs | Unique `(collector, run_key)` and `(job_type, job_key)` prevent duplicate control records. Runs allow failed → running retry. Job claiming is a conditional SQL update with a lease; succeeded jobs cannot be claimed again. |
| Evidence Freeze | Freeze version and canonical JSON manifest of raw record IDs/hashes are written once. SQLite triggers reject update/delete of a freeze. It contains no inferred research conclusion in Stage 0. |

## Canonical schema (`0001_foundation`)

| Table | Key / uniqueness | Important fields |
| --- | --- | --- |
| `raw_documents` | UUID; unique `(source, external_key, sha256)` | `external_id`, `relative_path`, `byte_size`, `media_type`, timestamps |
| `entities` | UUID; unique `(kind, stable_key)` | `display_name`, `status`, `deleted_at`, timestamps |
| `collector_runs` | UUID; unique `(collector, run_key)` | `status`, `attempts`, `last_error`, timestamps |
| `jobs` | UUID; unique `(job_type, job_key)` | `status`, `attempts`, `lease_until`, `last_error`, timestamps |
| `audit_log` | UUID | `event`, `object_type`, `object_id`, `details_json`, `created_at` |
| `evidence_freezes` | UUID; unique `version` | `manifest_json`, `manifest_sha256`, timestamps |
| `documents` | UUID; unique `(source, external_id)` | `cik`, `form`, `filing_date`, `source_url`, `raw_document_id`, soft-delete fields, timestamps |
| `contract_awards` | UUID; unique `(source, external_id)` | public `award_id`, recipient, amount, agency, modification date, `raw_document_id`, soft-delete fields, timestamps |
| `federal_register_documents` | UUID; unique `(source, external_id)` | title, type, publication date, agency names, `html_url`, `raw_document_id`, soft-delete fields, timestamps |
| `alembic_version` | migration revision | Managed by Alembic |

`0001_foundation` creates the foundation tables and guards. `0002_documents` adds SEC document metadata. `0003_contract_awards` adds contract award metadata. `0004_federal_register_documents` adds Federal Register metadata, a RAW foreign key, and a hard-delete guard. Schema changes belong in a **new Alembic revision**. `migrate` takes a verified snapshot before upgrading an existing, outdated DB. Repeating an already applied migration does nothing. Health and migration read the current Alembic head dynamically.

## Recovery and operational boundaries

- Raw publication happens before DB commit. A crash after publication can leave an **unreferenced, valid immutable blob**; it cannot leave a committed row pointing to an unpublished blob. Reingestion references the same content address. Staging temp files may remain after a hard process kill and can be reviewed separately. Stage 0 deliberately has no raw garbage collector.
- SQLite online backup snapshots the DB, then copies only raw blobs referenced by that snapshot. Every copy and the manifest are hashed; restore verifies hashes and SQLite integrity before publishing the restored directory. Backups are manual and local, without retention scheduling or off-device replication.
- SQLite supports one writer at a time. Conditional job claiming prevents a normal double claim, but an expired lease can be reclaimed while the prior worker is still alive; a future worker must check its lease before committing external effects. The system does not run concurrent collectors in Stage 0.
- Audit events are atomic for calls through `core.py`. Direct SQL writes outside the service boundary can bypass semantic audit events. Restrict write access to the application and migration process; stronger DB-level audit enforcement can be added with a migration when direct writers are introduced.
- Read-only health checks count all referenced blobs. `--deep` additionally hashes each, which takes time proportional to raw storage. Backups always hash referenced blobs.
- SQLite specific migration guards and backup code live at the persistence boundary. A new backend requires a new DB adapter, migration set and backup strategy; future vendor collectors can keep the same `Collector` contract.

## Stage 4 gate

Do not connect another API until the Stage 0–3 tests pass in the target environment and a backup containing SEC, USAspending and Federal Register records restores cleanly. Historical coverage and larger-scale search require explicit pagination, entity resolution and backup retention; these remain outside Stage 3.
