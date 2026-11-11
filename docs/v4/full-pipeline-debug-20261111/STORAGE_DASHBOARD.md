# Storage, REVIEW and dashboard audit — 2026-11-11

Task `BCT_V4_FULL_PIPELINE_DEBUG_20261111`; fixed plan `BCT-V4-Q-1.0`, Q1/Q2 PARTIAL. Objective Lock, original/frozen records and S gates remain unchanged. All restore/replay writes were under `/tmp`; no production database, remote ref, Secret, CPU pin or schedule was changed. Structured evidence: [STORAGE_DASHBOARD.json](STORAGE_DASHBOARD.json).

## Storage and exact access boundary

The current credentials can read the private repository, refs, Git blobs and Releases. Repository access is **not blocked**. The existing `BCT_V4_STATE_PASSPHRASE` and dedicated writer-token environment variables are absent from this local process; their values were neither requested nor printed. The latest monthly manifest/data are encrypted. Their actual plaintext restore and latest-generation numerical recount therefore remain **BLOCKED** in this environment. This is not a missing repository, a failed password, lost data or permission to initialize a replacement database.

| Current saved state | Observed evidence | Actual local restoration |
|---|---|---|
| Monthly quantitative primary | `bct-v4-archive-monthly-2026-10`, generation 6; 14 assets, 38,084,522 bytes; latest commit asset created October 16 12:54:26 UTC | BLOCKED: existing Actions passphrase is unavailable locally. The 3,202-byte encrypted generation-6 commit asset was downloaded successfully. |
| Previous quantitative Git anchor | `c87e8db9666387fa2d7346f43ac39c86bb45742b`; full checkpoint plus seven page deltas | PASS: hash-chain materialization, integrity and eight-table facts-only audit, then separate-process restore. SQLite SHA256 `8b725e750f95810f423fdfacc3432183f5403888cf0e6d31dbfbe15ab6d6c16c`. |
| Current CPU source-separated private ref | `1ea13ed1ff81b75f8c6216177c34bb04c0e088b5` | PASS: separate-process eight-table restore; SQLite SHA256 `dc2434510ec58e247c838353ad7c8d95f7f127161431ec55e4db1849f80fa7db`. |

The restored **older Git anchor** was freshly counted: 42,601 observation versions, 38,231 latest logical records, **38,046 numeric observations / 21,916 physical numeric observations**. Numeric sources: M3 540, G17 1,080, USAspending 8,498, EIA 18,745, TED 3,645, USGS 372 and Census trade 5,166. This corroborates the prior receipt at that anchor; it does not substitute for a generation-6 recount. The facts capsule contains zero source bodies, native files, CPU queues or LIVE firsts. It is not the full historical source database.

The preserved CPU checkpoint has 1,277 `CPU_RESUME_WINDOW` receipts, 41 completed keys, 20 prior reviews and 140 common-evidence records. Original bodies/quotes are absent by design. Restoring these receipts does not revalidate their original sources or rerun CPU inference.

Read-only source URLs: [monthly archive](https://github.com/irewon1-lgtm/bct-v4-private-state/releases/tag/bct-v4-archive-monthly-2026-10), [quantitative Git anchor](https://github.com/irewon1-lgtm/bct-v4-private-state/tree/c87e8db9666387fa2d7346f43ac39c86bb45742b), [CPU ref](https://github.com/irewon1-lgtm/bct-v4-private-state/tree/1ea13ed1ff81b75f8c6216177c34bb04c0e088b5). Access to private links requires repository authorization.

## REVIEW handoff, preservation and confirmed disk failure

The 43 REVIEW jobs since November 4 reconcile as follows:

- **39 actual frozen-intake executions and durable receipts:** 578 records, all `HOLD`; 703 skipped captures, all `CAPTURE_PROVENANCE_NOT_PASS`; zero alerts, semantic completions, first-review records, EARLY successes or LIVE writes.
- **Three successful workflow runs with intake skipped:** [42232550557](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42232550557), [42129057767](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42129057767), [41756797890](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/41756797890). Their saved-source handoff was unavailable. These are not successful semantic intake deliveries.
- **One failed handoff:** [42502046388](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42502046388), job `128796709021`. The actual log says `error extracting ... evaluations/<hash>.json ... no space left on device`. The upstream cache ZIP was 3,895,345,797 bytes. Frozen intake was skipped. Restore and persistence retained the identical review SHA `4f8b0f042563f598829e9b38bff95d2cd611a547`.

Latest [run 42942892140](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42942892140) received source run `42939818925`, produced two HOLD records, three source skips and zero alerts, then persisted `76ba081f… → 0ad6ba0a9a6cea0211c760b3e19502ad9e29a54c`. At that current review snapshot there are 197 durable run receipts and 2,837 queued/intake records, with zero semantic completions and zero first-review records. All **6,046 immutable files** in the downloaded snapshot matched the remote Git blob hashes; only the derived summary is excluded from that immutable check.

The minimal development fix changes transport only. `bct.review_artifact` downloads the existing ZIP temporarily, extracts only this acquisition's capture metadata and hash-addressed raw HTML, and leaves verification to the unchanged source loader/frozen intake. It does not expand evaluations or old raw files. It enforces a 6 GiB compressed limit, 256 MiB selected expanded limit, a 1 GiB disk reserve, a pre-download space check, exclusive destinations and archive cleanup. Current latest cache metadata is 4,598,165,007 bytes, below the compressed limit. Its selected expanded size is **NOT_MEASURED**: the 4.6 GB archive was not downloaded again for this audit. The next real Actions execution must verify the bounded transport receipt; operational recovery after this fix is **NOT_RUN**.

## One real saved-source local replay

One existing Aehr raw source was replayed without HTTP, CPU or AI calls: [official source](https://www.aehr.com/2026/07/aehr-receives-follow-on-production-order-from-lead-silicon-photonics-customer-for-fully-automated-fox-xp-wafer-level-burn-in-system/). Its raw/body hashes matched. Current raw extraction passed the existing provenance loader; bounded ZIP selection retained one capture and one raw file, **153,843 bytes**. That input passed handoff, source storage, SQLite backup, eight-table equality and byte-identical read-only restore in a separate process. Existing supply-review code accepted one source event and produced zero strict candidates. The copied existing frozen REVIEW state returned one HOLD and zero alerts; all 6,046 prior immutable files remained byte-identical.

Two guard outcomes are retained. Direct use of the frozen Aehr metadata was held because its date-only publication field differs from the timestamp returned by the current raw loader; the successful local input explicitly re-extracts that original raw and does not overwrite the frozen record. A separate exact DefenseNews source reload matched its stored proof fields but was correctly excluded by the existing corpus URL exclusion. No exclusion or frozen-source gate was bypassed. The successful replay is a local BACKFILL function proof, not new prospective research or independent performance evidence.

An initial byte comparison accidentally compared the live SQLite serialization against its SQLite backup and returned false. That result is retained in `/tmp`; follow-up verification established equality of all eight tables and an exact backup-to-restored byte match in a new read-only process. The evidence uses those specific measurements rather than treating live-file and backup serialization hashes as interchangeable.

## Deployed dashboard

[Live GitHub Pages](https://irewon1-lgtm.github.io/bottleneck-control-tower/) returns HTTP 200. Its manifest pins `23a0615f`, equal to the current integration code. Main `28d0b8c6` supplies the Pages publication workflow. The dashboard JSON bytes match the manifest and the published full progress JSON equals the repository's current progress. The verified code gate [38914608375](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38914608375) and Pages publish [38914878655](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38914878655) succeeded.

**Code freshness and data freshness differ:** source data is dated October 14; the snapshot was published October 16. The screen shows 38,046 numeric / 21,916 physical / 42,601 versions from saved receipts and exposes 1,703 detail records. Refreshing this static export does not read newer canonical data or encrypted monthly archives. Equality with current repository progress does not prove current acquisition has reached this research snapshot.

Browser checks passed for four desktop views, a real detail modal, refresh and four sampled detail endpoints; no JavaScript errors or mutating requests were observed. Mobile overview has a confirmed horizontal overflow: document width 402 px at both 390 px and 320 px viewports, caused by the unbroken quantitative status token inside `p.section-note`. A browser-memory test of `overflow-wrap:anywhere` removes the overflow, but no CSS/design change was made in this audit.

## Verification and continuation

Failure-first artifact regressions failed before implementation. Focused REVIEW/source-loader tests: **46 passed**. Including the preserved historical dashboard-manifest checks: **56 passed**, zero failed. The unchanged source verification path was tested against a real parser-generated capture, and the actual archived Aehr raw replay supplies separate end-to-end evidence.

Key read-only commands and local checks:

```bash
gh api repos/irewon1-lgtm/bct-v4-private-state/releases?per_page=100
gh api repos/irewon1-lgtm/bct-v4-private-state/git/matching-refs/heads
gh api repos/irewon1-lgtm/bottleneck-control-tower/git/trees/review-lead-shadow-state?recursive=1
.venv/bin/python -m pytest -q tests/test_review_artifact.py tests/test_review_shadow.py tests/test_review_frozen_transport.py tests/test_review_intake.py tests/test_review_leads.py tests/test_v4_post_ui.py
```

Restore code used the existing `quantitative_delta.materialize`, `quantitative_private.restore` and `cpu_operations.restore`, each against newly created `/tmp` destinations. Exact job-log evidence came through the connected GitHub job-log tool because direct redirected log downloads were blocked by this environment. No failed original source GET, paid service, model installation, storage stress test, schedule, CPU pin or Secret setup was repeated.

Next action: final aggregate verification and review of the development changes. Latest encrypted monthly restore must run in its existing secret-enabled read-only Actions context; the existing secret does not need to be recreated. Q1/Q2 remain PARTIAL; independent Q3 pairs, independent performance and LIVE discovery remain BLOCKED/zero.
