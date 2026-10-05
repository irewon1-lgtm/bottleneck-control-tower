# BCT v2 shadow contract

This implementation is isolated from v1 and production workflows. No collector,
LIVE session, Objective Lock, strict/S gates or v1 code is changed. The entry point
is `python -m bct.shadow_v2`; it invokes `precursor_v2.evaluate_pair_v2` through
`synthesize`. Aggregation and freeze consume the same sealed decisions. It never
calls v1 `prospective.run`.

## Evidence and decisions

Ordinary source predicates, explicit model/manufacturer, product/specification,
contract/facility and qualification identifiers retain exact original offsets.
Supported time expressions are ISO dates, years and explicit calendar halves.
Unsupported grammar, fiscal/relative periods, ambiguous entities and multiple
unattributed dates remain UNKNOWN. There is no industry TARGET dictionary,
similarity score, external API or automatic inference from company domicile.

Adjacent sentences share fields or role-specific periods only through explicit
matching identifiers and namespace, with no conflicting contract/facility/model.
Aliases require an original explicit equivalence statement. Required components
are directional edges with an explicit component need period; no BOM ratio is
invented and finished-product quantities are never compared with component output.

Same product/model does not prove regional, customer/allocation or qualification
applicability. A supply's qualification must be tied to the observed required
certificate through certified capacity or qualification completion evidence.
Unknown totals permit a source-backed readiness lag; unknown applicability blocks.
Non-overlapping periods can establish lag. Overlap alone never establishes lag.
Quantities require matching units, basis and comparison period with qualified,
contract-allocated supply. Nominal market capacity cannot stand for allocation.

Actual confirmations are separate facts even in another paragraph. Negated,
forecast or incompatible-model statements never exclude the whole source body.
Uncertain scope/date attribution is POSSIBLE_PRIOR_CONFIRMATION and blocks EARLY.
Cancellation, reconciled delay and sufficient qualified alternatives are evaluated
in the same gate. Serialized original provenance is a trusted archive input;
independent source authenticity must not be inferred from successful grammar parsing.

## Epoch and persistence

Use a new explicit shadow directory, never a v1 LIVE path. Activation binds v2
and shared dependency file hashes. A changed binding fails closed and requires a
separate epoch. First shadow records are immutable, replay-idempotent and distinct
from LIVE first_detected_at. Later confirmation/refutation is append-only history.
Source input, decision and record digests are stored. There is no manual timestamp
argument on the entry point or LIVE performance claim.

Example (paths are private diagnostic outputs, not tracked original article bodies):

```bash
PYTHONPATH=src .venv/bin/python -m bct.shadow_v2 \
  --input /workspace/bct-v2-shadow-20261005/input.json \
  --gold /workspace/bct-v2-shadow-20261005/gold.json \
  --seal /workspace/bct-v2-shadow-20261005/input-gold-seal.json \
  --store /workspace/bct-v2-shadow-20261005/epoch-validated
```

## Comparison boundaries

Gold source spans and labels are frozen before outputs. Both versions receive the
same unchanged original bodies without enriched scope labels. The v1 comparator
runs in BACKFILL mode for diagnosis and writes no v1/LIVE records. Document,
event and pair counts have separate denominators. Link and EARLY metrics are
separate; abstained certain positives remain false negatives. Uncertain labels
are reported separately.

The current preserved-original diagnostic has six single-reader hard-negative
cases and two uncertain cases, with zero confirmed positive links. It therefore
cannot establish recall, precision or performance PASS. Functional synthetic
tests are explicitly separate and are not original-source performance evidence.
The exact binomial helper is only appropriate for independent adjudicated units;
source/contract clusters must be grouped before claiming its bounds. Independent
second-reader labels, sufficient samples and an independent holdout are unverified.

Failed-request retry policy remains a separate production blocker and is not
implemented here. Main/LIVE rollout is not part of this change.
