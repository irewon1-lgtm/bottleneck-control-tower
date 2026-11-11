# Bounded REVIEW recovery verification

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`, plan `BCT-V4-Q-1.0`. Development
base `42ee0a6`; actual execution code
`bd9ee61092b0b94131fd7879874d50c8d385a872`. Operational main remains
`28d0b8c648c0218ab2e74a1fa04ca8d63e659933`.
**Actual development Actions transport replay passed.**
[Run 42990692268](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990692268)
was dispatched exactly once and completed in 5m25s. Its small receipt was
downloaded and its ZIP digest verified. Semantic review remains pending.

The existing development transport limits extraction to capture metadata
from the selected acquisition window and its referenced raw originals. The
new manual job uses that module, verifies the downloaded artifact's exact
digest, then runs the unchanged frozen REVIEW intake against a temporary copy
of the pinned review state. It repeats the delivery to test deduplication,
checks that all original copied files remain unchanged, and verifies the new
copied state hashes in a fresh process. Only the numeric/hash receipt is
uploaded. Neither source cache nor copied review state is published.

A separate `PRE_INTAKE_REPLAY` uses the exact historical parent
`76ba081f28aa9fcce639af87c8e0e57ba0a76bb0`, before the latest intake. It must
produce at least one new HOLD in that temporary copy, then deduplicate a repeat
and pass fresh-process hash verification. The current-state copy may correctly
return only duplicates. These two counts are reported separately; neither
changes the operating review state or represents semantic completion.

| Stage | Input/condition | Current result |
|---|---|---|
| Bind actual saved input | [Acquisition 42939818925](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42939818925), main `28d0b8c6`, success, created `2026-11-11T01:33:31Z` | PASS, read-only live metadata check |
| Bind artifact | `precursor-private-cache`, ID `13821760877`, 4,598,165,007 compressed bytes, digest `949e95d2efda7a3fd3e7a124eb0d6569b56b54dcd1a3d5fd7f053dc75b8dfb72` | PASS, actual download and digest match; temporary ZIP removed |
| Bound extraction | Five capture records and five referenced raw files; 1,074,585 expanded bytes within 268,435,456-byte cap | PASS; historical cache/evaluations not expanded |
| Verify actual source handoff | Existing frozen proof loader | PASS; two verified documents; three `CAPTURE_PROVENANCE_NOT_PASS` skips |
| Current-state copy | Exact Git SHA `0ad6ba0a9a6cea0211c760b3e19502ad9e29a54c` | PASS; two existing HOLD duplicates, zero new intake/semantic completions; 6,046 old files preserved |
| Historical parent copy | `PRE_INTAKE_REPLAY` at `76ba081f28aa9fcce639af87c8e0e57ba0a76bb0` | PASS; two new HOLD records in copy, then two duplicates and zero new records on repeat; 6,040 old files preserved |
| Regression before implementation | New helper/job absent | Expected FAIL, four tests |
| Related regressions | New wrapper guards/counting plus existing bounded artifact, frozen transport, shadow and intake checks | PASS locally and in actual Actions; 40 tests per run; independent review found no material issues |
| Fresh-process readback | Core-state file hashes after intake and duplicate delivery | PASS in both copies; original files unchanged |
| Receipt download/readback | Artifact `13842175964`, 24,797-byte ZIP; SHA-256 `325ac47defc421728f4b883e534c25914285ea6025e21a4f3a0d4118c07cdb54` | PASS via GitHub connector; direct CLI 403 retained as a separate access failure, no identical retry |

The executed command was:

```bash
gh workflow run bct-isolated-review.yml \
  --repo irewon1-lgtm/bottleneck-control-tower \
  --ref codex/bct-v4-integration -f bounded_current_replay=true
```

The bounded job requires the exact development ref and `workflow_dispatch`.
Its token has only `contents: read` and `actions: read`. It invokes no state
publisher, CPU model, semantic AI API, operational DB writer or LIVE discovery.
Existing review activation seals, frozen executable equivalence and original
source verification remain required. A processed HOLD/PENDING record is intake
work and is never counted as semantic completion. All actual saved inputs are
reported as REPLAY; new records in the temporary copy are not new operating
discoveries.

The ZIP central directory declares 51,460,031,534 expanded bytes, including
49,054,341,364 bytes under `evaluations/`. This explains why expanding the
whole saved cache exceeds a small runner's disk budget. The bounded REVIEW
path expanded only 1,074,585 bytes; it did not read or expand those evaluation
bodies.

The independent bounded inventory also located the exact historical fixed230
snapshot: 230 selected document metadata records reproduce fingerprint
`acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec`.
All 230 stored body hashes and all 230 referenced raw hashes matched; raw bytes
read were 38,607,847, with zero missing originals. Historical raw files were
streamed for hashing and were not extracted or uploaded. This identifies an
intact existing source copy. It does not rerun source provenance/semantic QA,
CPU processing, Gates0–6 or independent performance evaluation.

Conditions, file hashes, commands and actual stage counts are recorded in
[REVIEW_RECOVERY.json](REVIEW_RECOVERY.json). The exact downloaded, Objective
Lock-stamped result is [REVIEW_ACTIONS_RECEIPT.json](REVIEW_ACTIONS_RECEIPT.json),
SHA-256 `1e7c8fcd39e49c6a923a36f85c81684a32545452510b6d542050179f6370a413`.
The operating review ref stayed unchanged. Operating main transport application
and actual semantic completion remain separate work.
