# Actual six-source check before CPU

Label: **actual saved-source deterministic local replay; new CPU inference NOT_RUN**. No CPU read completion or read-HOLD is claimed.

Artifact `13861572513` from acquisition run `43032565649` attempt 1 has 1,310,662 ZIP bytes and exact SHA256 `10d2fa55dc913e1b1e972c790355681f13a8e0c3883123aa8763a46e8ede172f`. C2 `7afb1a25590ff604fd6293d237877f456b7f62b0` verified run/head/attempt, all 30 literal file sizes/hashes, manifest bindings, and all six metadata/body/raw/source-version identities. A fresh second extraction and post-check file-vector verification also passed. Native source validation used only a temporary queue; model loading and socket creation were denied.

| Exact document ID | Body characters | Planned windows | Planned characters | Held contexts | Located events | Deterministic source-only result |
|---|---:|---:|---:|---:|---:|---|
| `270bbad5-f286-4b2a-8947-7894ee0b2cb1` | 2381 | 10 | 2372 | 0 | 3 | TARGET_FIELDS_UNKNOWN |
| `f44f41fa-c3e1-4733-aa7b-7a1d9b692d4c` | 3185 | 15 | 3171 | 0 | 0 | DETERMINISTIC_PARSER_NO_LOCATED_EVENT |
| `8072e2a9-335c-4aae-9e8f-4ef84352f058` | 4409 | 20 | 4390 | 0 | 0 | DETERMINISTIC_PARSER_NO_LOCATED_EVENT |
| `2ba601cd-5903-4fad-8308-1ccfcf88286b` | 5773 | 17 | 5757 | 0 | 1 | TARGET_FIELDS_UNKNOWN |
| `d98ed8e2-7368-44c4-97e1-3b056f93e971` | 6472 | 21 | 6452 | 0 | 1 | TARGET_FIELDS_UNKNOWN |
| `35174258-db9a-4a0b-a6cf-4d0c734d1734` | 11603 | 49 | 11555 | 0 | 3 | TARGET_FIELDS_UNKNOWN |

Track shortest source `270bbad5-f286-4b2a-8947-7894ee0b2cb1` in the later actual CPU run: 2381 body characters, 10 planned windows, 2372 window characters, no held context. The nine omitted characters are paragraph newlines, not an unhandled linked context.

Exact body/source version: `3515cd52456dbeff0cc3bd7445019527b2be17be7fa80a1dd504ec3112bc3d6e`. Exact native SHA256: `7b55987303f90028af724ada5682588652f1696c09d79cf89c387ab298106542`.

The actual-source deterministic graph retains eight located parser events, all blocked with `INCOMPLETE_TARGET_SCOPE`. First blockers are `NO_SOURCE_BOUND_SPECIFICATION` (3) and `NO_SOURCE_BOUND_PRODUCT` (5); each event retains its ID, locator, first blocker, all missing TARGET fields and secondary missing fields in the JSON. The shortest source has three events: two lack specification/customer group/supply pool (one also lacks region), and one lacks all five TARGET fields. The other two sources with zero parser events are not labeled model-read no-event.

All six sources are preserved together: **33,823 body characters, 132 planned windows, 33,697 planned window characters, zero held contexts**. The literal CPU manifest has 18 rows; six have exact source originals in this artifact. The other rows are outside this six-source diagnostic and are not filtered or rewritten.

Available-source import order follows the unchanged literal CPU manifest: `35174258…` (manifest position 1, 49 windows), `f44f41fa…` (position 8, 15), `270bbad5…` (position 9, 10), `8072e2a9…` (position 10, 20), `2ba601cd…` (position 11, 17), `d98ed8e2…` (position 12, 21). The tracked shortest source is third among the six available sources, ninth in the literal manifest. Existing round-robin/window/time budgets remain unchanged; actual completed counts must come from later receipts, not this plan.

Combined graph: complete TARGET events 0, independent pairs 0, candidates 0. Existing Q3/strict-forecast route: eligible pairs 0, candidates 0, formal Q3 completion false. All six roots have a verified complete producer context manifest with no required counterpart sources. No quantity, qualification, independent pair, S2, S3, model result, or semantic completion was invented.

Model calls 0; new CPU windows 0; source HTTP requests 0; paid API calls 0; operational/private checkpoint writes 0. Remote dedup, actual inference, durable ACK, and full-source CPU coverage must be established by the later operating CPU job.

Source-free evidence: `ACTUAL6_SOURCE_REPLAY.json`. The downloaded ZIP and extracted originals remain in temporary local storage only.
