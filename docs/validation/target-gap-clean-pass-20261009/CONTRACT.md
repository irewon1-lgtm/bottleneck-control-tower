# Same-TARGET gap verification contract

Baseline: `ca3ac0b3ffc5ee548b63c9aa75adbbdd798acbc3` (PR #34 included).
This contract is fixed before new code or tests run. Actual EARLY findings are
measured separately from implementation verification and are never manufactured.

| Gate | Input and execution | Required PASS condition |
|---|---|---|
| 0 baseline | Current main, all Python/JS tests, engine/objective hashes, current remote refs | Existing required tests pass; existing skip remains explicitly unresolved; code/data baseline retained |
| 1 source extraction | Frozen official source bodies and source-addressed selected gold, plus negative relation cases | All labelled positive spans recognized; multi-product bindings, unnamed customers, pending/irrelevant qualification and missing fields cannot create unsupported TARGETs |
| 2 identity | Same contract/model/customer/specification relation cases and real documents | Every link has verified source references; conflicting/customer-local relations cannot propagate; no future, unverified or public-confirmation support can enter a candidate |
| 3 time and quantity | Same-TARGET source-bound need/readiness/quantity/relief cases | Same product/customer/eligible pool/unit/basis/period only; no shipment date treated as readiness, planned CAPA treated as available, or partial supply treated as sufficient; preserve UNKNOWN |
| 4 clean regression | All required Python/JS tests and actual source replay, fresh output directories | Gates 0–3 pass together on the same final code; protected engine/objective/history remain unchanged; repeat metrics deterministic excluding runtime timestamps |
| 5 prospective evidence | Newly acquired configured RSS/official sources with collection cutover and original provenance | Actual independent complete TARGET and supported 12–36 month gap before public shortage confirmation; BACKFILL/replay excluded. Zero findings do not pass this performance gate |
| 6 persistence | Tested commit, remote CI and immutable evidence | Verified code saved without force push or data-history rewrite; required CI passes; performance limitations retained |

On a code FAIL retain evidence, fix the cause, rerun the failed gate and all
invalidated dependencies. The final clean run always starts at gate 0. On a data
or access barrier record BLOCKED with the exact missing evidence; do not lower
criteria, fabricate eligibility, relabel historical data as LIVE, or repeat the
same request indefinitely. No private-derived queries go to external search.

Full objective success requires gate 5. A passing implementation is not proof of
future shortages or lead-time performance. Existing pre-public holdout SKIP is
not a PASS and must remain visible.
