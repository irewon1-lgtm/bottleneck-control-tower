# Bounded REVIEW recovery verification

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`, plan `BCT-V4-Q-1.0`. Development
base `42ee0a6`; operational main remains `28d0b8c648c0218ab2e74a1fa04ca8d63e659933`.
The current status is **prepared; actual Actions execution NOT_RUN**. The job
must run and its receipt must be downloaded before transport recovery can be
reported as verified.

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
| Bind artifact | `precursor-private-cache`, ID `13821760877`, 4,598,165,007 compressed bytes, digest `949e95d2efda7a3fd3e7a124eb0d6569b56b54dcd1a3d5fd7f053dc75b8dfb72` | PASS, metadata only; download NOT_RUN |
| Bind copied review state | Exact immutable public Git SHA `0ad6ba0a9a6cea0211c760b3e19502ad9e29a54c` | Selected; restore NOT_RUN |
| Regression before implementation | New helper/job absent | Expected FAIL, four tests |
| Related local regressions | New wrapper guards/counting plus existing bounded artifact, frozen transport, shadow and intake checks | PASS, 40 tests |
| Actual bounded extraction → verified-source handoff → copied-state intake → duplicate delivery → fresh-process readback | GitHub standard Ubuntu runner, manual development ref only | NOT_RUN |
| Actual receipt download | Run URL/artifact not yet created | NOT_RUN |

Dispatch the existing workflow after this code is pushed to development:

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

Within the same temporary ZIP, an independent bounded inventory may identify
the historical fixed230 metadata vector. Date selection alone is insufficient:
the exact original fingerprint must match before referenced historical raw
bytes are hash-checked. This optional result cannot turn the current REVIEW
test into a source-quality, CPU, Gates0–6 or independent performance PASS.

Conditions, file hashes, commands and pending actual run fields are recorded in
[REVIEW_RECOVERY.json](REVIEW_RECOVERY.json). The actual result must replace
the NOT_RUN rows after the run and receipt readback finish. Operating main
transport application remains a separate reviewed change.
