# Single origin-count BACKFILL diagnostic

The original Objective Lock and v2 engine are byte-preserved. This is an isolated
counterfactual diagnostic, not a new EARLY definition, discovery run, LIVE freeze,
performance test, or retrospective first detection.

## Original identity, input and selection

The 7 source/dependency hashes in the original batch activation and the current
prospective activation exactly match the actual checkout. The origin-preservation
commit is `4ad92a8`; it includes the previously untracked v2 modules and tests,
raw HTML/provenance for the four primary originals, original byte-identical inputs,
summary/configuration and the full immutable receipt (gzip; original hash sealed).
The original immutable receipt passes its Objective Lock and record-digest checks.
`original/run-presentation.json.gz` is the prior CLI presentation with an extra
loader report; it is deliberately distinct from the immutable receipt.

The 17 pair IDs were selected by `relation.state == VERIFIED` from 12,660
combinations, after 52 documents had passed document validity/provenance checks.
They are NOT 17 source-independent cases. There are 4 distinct document identities
and 4 source-bound product/project/model labels, but **zero formal TARGET IDs**.
The counts are 3 hydrogen/Katy, 1 PrSM Increment 2, 1 eActros 600 and 12 Hemerdon.
All 17 are within-document pairs (one observed article origin each).

The 48 other retained documents and all 302 saved events stay unchanged as
refutation/confirmation context. They do not become extra experimental pairs.
The 12,643 other combinations, provenance failures and preselection losses are
out of this comparison's scope. `original/input-inventory.json` records original
PASS-body/metadata exclusions; no excluded sample is silently added or repaired.
There is no inference from this conditional sample to BCT as a whole.

## Every inspected source/independence location

| Location | Actual role | Diagnostic handling |
|---|---|---|
| `shadow_input_v2.load_documents`, `_verified_proof` | Saved PASS proof/body/version/metadata binding; no minimum origin count | Unchanged original archive input; proofs preserved |
| `precursor_v2.validate_document` lines 66–74 | Body/version, provenance/identity, publication/availability | Unchanged A and B |
| `extract` lines 279–350, `DIRECT_REQUOTE` line 31 | Stores direct-origin/requotation flag per event | Uses identical saved events; no values edited |
| `relationship` lines 354–411 | Product/model/facility/contract relationship; same-document namespaced identity can pass | Unchanged; identity is not independence |
| `_independent` lines 414–420 | Direct-origin checks; normalized origin ID/URL/publisher/body/family inequality; distinct quotes | Original function and observed result preserved |
| `evaluate_pair_v2` line 443 | Records `_independent` result | Same actual false values in both outputs |
| `evaluate_pair_v2` line 463 | Adds blocking reason for failed independence | The ONLY changed AST predicate in isolated B; keep direct-origin and distinct-quote failure blocking |
| `synthesize` lines 566–576 | Eligible documents → DEMAND×SUPPLY combinations → common evaluator; no `len(origins)<2`, no `strict.independent` call | Selected stored pair IDs and full saved context used directly, without selection changes |
| `counters` lines 585–587 | Reports observed independent/scope/gap counts | Not changed or reinterpreted as an additional eligibility gate; actual observed independence remains false |
| `counters` lines 588–589 | Counts evaluator `early_eligible` / unique IDs | Original definition preserved; diagnostic count reads the same eligibility field, not intermediate counts |
| `shadow_v2.freeze` lines 68–93 | Consumes sealed evaluator decisions/IDs; no additional origin gate | Not invoked; no candidate/history freeze or backdate |
| `shadow_v2.run` lines 96–111 | Same evaluator, activation hashes, current clock, immutable receipts | Not invoked for BACKFILL comparison; original as-of is sealed and explicitly diagnostic |
| `shadow_v2.compare` | Separate link-performance benchmark/gold adequacy | Not this diagnostic; no performance PASS claim |

No v2 TARGET-level `len(origins)<2` nor v1 `strict.independent` call is present in
this actual evaluation path. The declaration of two independent origins in the
Objective Lock is preserved; hashes are checked, not rewritten. The two
cardinality/family subchecks inside `_independent` are not skipped by forging
independent=true. Instead B suppresses only their blocking consequence when all
other source safeguards pass. The synthetic positive test proves a same-original
eligible pair can reach B's final eligibility, so another hidden source gate does
not silently negate the diagnostic. That synthetic result is not corpus evidence.

## What DATA_WAIT actually retains

The immutable `shadow-epoch/runs/*.json` contains full `prepared.documents` (bodies,
IDs, origin identity, publication precision, availability/hash), `prepared.events`
(roles, facts, fields, offsets, quotes and context), and `prepared.evaluations`
(pair IDs, provisional pair ID, reasons, UNKNOWNs, windows, comparison, refutation,
prior confirmation and evaluation time). The summary exports only selected labels
and snippets. It is not the authoritative full saved input.

For these 17, `target_id` and `target_name` are null. There are no per-TARGET
candidate/first-shadow-freeze/history files in this epoch; DATA_WAIT is retained
in the run receipt. No `first_detected_at` is reconstructed or inferred. Dates
for the evaluation are retained, not original prospective candidate dates.
The original v2 receipt has no formal `T_scope`/frozen confirmation-source-universe
field or `T_global` determination; those remain UNKNOWN in this diagnostic.

## Experiment validity and isolation

Original-preservation commit: `4ad92a8`.
Pre-output diagnostic-code/review commit: `c2f072e`.
`manifest.json` seals the relation/document IDs, code hashes, stored extraction
hash, as-of, selection policy, commands and stop rule. `diagnostic-seal.json`
seals the diagnostic function/runner, original-input bytes and independent source
review before the A/B comparison. Both A and B use the same saved extractions;
the existing deterministic `_validate_event` reconstruction is integrity validation,
not a new AI extraction or replacement of stored values.

There was **one valid A/B comparison and no invalid comparison attempt**.
A reproduced all 17 original saved decisions exactly. An AST reversal proof
shows exactly one conditional expression changed; all other AST nodes match.
Outputs also assert all fields besides the permitted reason/final consequence/hash
are identical, including independent, windows, comparison, evidence, target and
refutation/confirmation. Nine synthetic minimum isolation checks passed.
Source gate waived for 16 pairs; PrSM's saved `direct_origin=false` remains blocked.
All 17 A/B outcomes remain DATA_WAIT. Counts: **A=0, B=0, additional=0**.

No production code, dependency hash, input archive, original v2 epoch, LIVE
session, collection schedule, DB, Actions configuration, main or public app was
modified. The new diagnostic artifacts are on a separate branch only.

## Full-source reading and T

All four full preserved bodies were read. All 34 selected event quote spans match
both the stored body/offset and retained raw HTML. Source-review observations have
independent original-body hashes and locations. No correction is injected into
fixed events. The detailed per-pair table distinguishes PASS/FAIL/UNKNOWN and
NOT_EVALUATED. Missing periods cause time/quantity comparison branches to be
NOT_EVALUATED, rather than presumed passing after the first blocking condition.

- Hydrogen: 500 kg/day nominal capacity and expansion to 2 MW by end-2026 appear;
  they are not qualified allocated supply or a dated demand requirement.
- PrSM: awarded contract appears elsewhere but selected event is a company
  requotation. 2027 flight testing is not delivery/qualified-readiness timing.
  The document explicitly reports missile shortage; general PrSM lacks exact
  Increment 2 scope, so document confirmation=YES, same-TARGET confirmation=UNKNOWN.
  Its publication is recorded as an observed confirmation-bearing article, not
  the earliest T. The frozen evaluator says NONE_OBSERVED; this is not proof of
  globally absent prior confirmation.
- eActros 600: the demand event is rhetorical “in order to build the ecosystem,”
  an extraction semantic error, not a confirmed order. Lowliner/NextGenH2 periods
  cannot be transferred to eActros 600. 2024 series production is historical.
- Hemerdon: >1,000 tonnes/year and Q1 2027 full-production ramp target are present.
  Current period grammar does not support quarter/end-of-quarter syntax. The
  offtake start/need date, qualified-ready status and allocated qualified amount
  are not established by these statements. “if supplies exist” stays conditional.

Existing `prospective.observe` lines 270–307 require frozen source universe,
explicit same-TARGET match and exact verified publication before recording scoped
confirmation. Neither T_global nor a qualifying first T_scope is established here.
All 17 T/T_scope values stay UNKNOWN; no public date replaces a freeze date.
The same 52-document saved context contains no additional body with these literal
TARGET names beyond the four primary originals. That limited text inspection is
not proof of no aliases, external available evidence or historical public facts.

## Conclusion and next action (proposal only)

**이 고정 입력에서 출처 수만 완화한 효과가 확인되지 않았다.**
This does not establish lack of historical information, failure of acquisition,
meaninglessness of independent-source requirements, or actual early-detection
performance. Simultaneously blocked: qualification 17, allocation/applicability 17,
qualified readiness binding 17, explicit need/readiness period 17, region 16,
committed demand 11. No tuning, re-sampling, field correction or rerun followed.

One next minimal action: separately test interpretation of the already preserved
Hemerdon “by the end of the first quarter of 2027” ramp statement with its scope
and precision intact. Explicit text is available but unsupported by the frozen
period grammar. This proposal does not infer certified readiness or fill missing
demand dates, and was NOT implemented in this diagnostic.
