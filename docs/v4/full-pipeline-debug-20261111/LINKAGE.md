# Q2/Q3 linkage evidence — 2026-11-11

Task `BCT_V4_FULL_PIPELINE_DEBUG_20261111`; plan `BCT-V4-Q-1.0`; base
`23a0615f1a10f2b938cb2b5401706a1995b4d4f2`. Current master status remains Q1
partial, Q2 research partial, actual qualified Q3 pairs blocked. This is scoped
debugging evidence, not a new plan or a Q3 completion claim.

The confirmed silent TARGET loss is fixed as a diagnostic defect. Every
incomplete precursor now retains its document, event and observation IDs,
ordered first blocker, all missing fields, secondary missing fields and field
reasons. Unbound observations are also explicit holds. `q3_input` returns these
graph holds to its caller. No incomplete event becomes eligible.

The unchanged source-bound graph → Q3 → forecast route works on a synthetic
timing fixture with quantities `UNKNOWN`. Scalar structured eligibility alone
still cannot enter this route. It now reports
`STRUCTURED_PAIR_SOURCE_BINDING_REQUIRED`, with the exact missing contract:
native source-fact to graph-event binding, located TARGET/temporal references,
and verified graph supply qualification/coverage. No new automatic adapter was
introduced. A graph result and an unrelated scalar precheck remain separate
results even when supplied in the same call.

| Check | Execution/conditions | Result | Evidence |
|---|---|---|---|
| Audit diagnosis | Read `2aaaa91f` via `git show` | PASS, scoped source review | `ROOT_CAUSE_REPORT.md`, `STAGE_LOSS_EVIDENCE.csv`, `CODEX_MINIMAL_FIX_SPEC.md`; `STAGE_LOSS.md` does not exist at that commit |
| Before reproduction | Base reader/code; seven stored body snapshots; SQLite `mode=ro` | Confirmed defect | 59 precursor events → 0 complete TARGETs / 0 pairs, with `blocked=[]` |
| Red regression | New focused tests before production edits | Expected FAIL | Five diagnostic tests failed; existing timing and ready-before-need controls passed |
| After actual replay | Same seven bodies; combined worktree includes separate product-reader repair | PASS for trace preservation | All 59 incomplete precursor events have ID/blocker traces; actual complete TARGETs/pairs remain 0/0 |
| Actual saved official scalars | Existing 30-event packet; source originals unavailable for this replay | Scoped replay only | 18 accepted demand events, zero accepted supply events; 18 `LINKAGE_NO_VERIFIED_OPPOSITE_SIDE` holds; candidates 0 |
| Timing without quantities | Synthetic located independent documents, complete TARGET, explicit total basis, qualified supply covering all committed demand, need 2028 / ready 2029 | PASS, functional only | Two graph signals, quantities `UNKNOWN`, one Q3 pair and one strict forecast candidate |
| Supply coverage unknown | Same synthetic dates; whole qualified supply coverage absent | PASS, safe hold | Graph timing pair exists; Q3 reports `SUPPLY_UNKNOWN` / `QUALIFIED_ENTIRE_SUPPLY_SCOPE_UNPROVEN`; strict candidates 0 |
| Supply before need | Synthetic need 2028 / ready 2027 | PASS, safe hold | Strict candidates 0 |
| Scalar-only structured pair | Complete synthetic scalar TARGET/quantities pass existing quantitative precheck; no source graph documents | BLOCKED, explicitly diagnosed | Structured precheck pairs 1; graph/Q3 forwarded pairs 0; missing source binding contract retained |
| Focused regressions | Current worktree; graph, official discovery, forecast and new linkage tests | PASS | 97 passed, 1 skipped; skipped real pre-public holdout remains unavailable |
| Protected contracts | Byte comparison against base and AST comparison of official producer/save functions | PASS | Objective Lock, strict forecast and EARLY bytes unchanged; `extract_ocds`, `indicative_supply`, `read_context`, `save`, `enqueue` unchanged |

The after replay's first blockers are product unknown 49, specification unknown
9 and region unknown 1. These are ordered diagnostic categories across 59
events, not exclusive claims about root causes in the wider corpus. Secondary
missing fields remain in [LINKAGE.json](LINKAGE.json). That file records input
hashes, all 59 event traces, before/after counts and synthetic outcomes.

Verification command:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_v4_q3_linkage_trace.py tests/test_precursor_evidence_graph.py \
  tests/test_v4_official_discovery.py tests/test_forecast_discovery.py
```

The actual replay used the read-only temporary database
`/tmp/bct-extraction-20261111/reading-quality.sqlite3`; integrity was `ok`, all
seven body hashes matched, and database SHA-256 stayed
`a21227317a8d24225b54541e7a250138359b21793a64a19778db2abf3d0c4d29`.
This small reading-quality subset is not the latest complete research database.
No stored original, operational state or external service was changed by this
work; source HTTP requests and AI calls were zero. S2/S3 remain 0 and
`formal_Q3_complete=false` for every Q3 result.

Scoped implementation and functional verification are complete. Actual complete
qualified-pair transport and independent pre-public performance remain BLOCKED
until matching real source facts, their verified graph binding, and suitable
independent evaluation inputs exist. The next linkage step is to supply that
specific evidence contract; synthetic transport does not establish live
discovery or real forecast performance.
