# Pre-public precursor discovery

This additive path keeps Objective Lock, `early_forecast.py`, strict
`forecast_discovery.py`, S3 review/comparison, and CAS ownership unchanged.
Existing TARGETs and historical first records are never rewritten. No score,
paid API, investment advice, collector expansion, or backdated detection is added.

## Audit

The old collector already retains demand/supply/relief leads without requiring a
shortage word, but extracts TARGET nouns inside individual documents. The EARLY
engine requires supplied TARGET IDs and verified scope relations; it does not
synthesize a composite TARGET. Some legacy pending statuses accept an UNKNOWN
supply window. The new route enforces both future windows and explicit timing or
physical quantity tension before invoking the legacy engine. Legacy input keeps
its existing behavior and all existing tests.

## Source-addressed inputs

`precursor_discovery.extract_events()` preserves procurement, reservations,
prepayments, customer CAPEX, deployment, policy/origin restrictions, DPA/DoD
investment, factories, commissioning, qualification, inventory, lead-time,
concentration and substitute events. Source paragraphs, offsets, raw windows,
quantities/units and field references are retained. Absence of shortage words
does not filter these leads. Unverified provenance or incomplete scope stays a
lead, never verified evidence.

Five physical attributes form a new TARGET identity: product, specification,
region, customer group and qualified supply pool. Literal unique source labels
can be read automatically, for example `product: ...; specification: ...; region:
...; customer group: ...; supply pool: ...`. For normal prose, a source reader can
supply `document.precursor_events`, with each `scope` field represented as
`{"value":"literal source value", "locator":{"start":0,"end":20}}`.
All values and event quotes must match source bytes. Customer, region, product or
pool context is not guessed from a publication domain. Without source-bound
attributes, ordinary prose remains unresolved; this is a concrete corpus blocker,
not evidence that such articles establish an EARLY candidate.

A `VERIFIED_SUPPLY_CHAIN` relationship can associate a component with another
product only when both product names and their relationship appear in a verified
source, the other physical attributes match, and the component's actual required
window is source-addressed. Product quantity is never converted into component
quantity. Different specifications, regions, customer groups or pools cannot be
joined. There is no issuer-specific TARGET template.

## EARLY and refutation

At least one committed incremental demand event and one independently sourced
supply/ramp constraint are required. Both have explicit source windows. The
sources must be independent by original identity, URL, publisher, body and quote;
multiple releases from one company do not create multiple origins.

Possible timing tension requires a source-window lag, source-proven exact need
and readiness dates, a stated readiness range crossing the need deadline, or an
explicit possible missed demand window. Same-year pending construction alone
is insufficient. Quantitative tension requires comparable physical units,
accepted bases and source-qualified supply, using unchanged strict comparison.
Coarse source windows retain their precision and never become exact need dates.
No dollars/MW-to-output conversions, quantity sums or inferred relative dates.

Unknown absolute totals do not suppress a valid timing-based EARLY candidate.
Missing provenance, independent demand/supply origins, physical relation,
future windows or explicit tension produce DATA_WAIT/unresolved leads.
Sufficient same-scope qualified supply/substitutes/inventory before need refute
the hypothesis; same-scope cancellation or deferral blocks promotion until
reconciled. Government investment by itself does not establish a constraint.

Explicit public shortage material is routed to confirmation, not first evidence.
A verified prior public confirmation yields MISSED_EARLY_DETECTION. After an
actual frozen first, a later verified timestamp yields CONFIRMED. The existing
frozen publisher universe is preserved for stored confirmation. Missing exact
confirmation time is not filled from a date. Original first bytes are preserved;
followup/refutation/confirmation evidence is append-only.

## Entry points

The existing LIVE snapshot adds `precursor_events` beside its unchanged source
metadata and exact cache pointer. Extraction does not assert provenance.

Read-only validation of an existing objective-stamped verified batch:

```bash
PYTHONPATH=src .venv/bin/python -m bct.precursor_discovery \
  --input /path/to/batch.json --output /path/to/new/read-only-result.json
```

For a `source-inputs.json` artifact, add `--artifact-root /path/to/artifact`.
This reuses `future_body.discovery_document()` and its body-bound provenance and
publication guards. Original RSS dates are not promoted to original publication.

Freeze only into an already existing LIVE store:

```bash
PYTHONPATH=src .venv/bin/python -m bct.prospective \
  --store /path/to/existing/store run-precursors --input /path/to/batch.json
```

The module also accepts `--store` for artifact inputs, but refuses a missing
session. It reuses the existing atomic first writer, append-only histories,
source snapshots and strict engine binding. A DATE remains a DATE in first
records. The precursor implementation hash is recorded alongside the unchanged
legacy EARLY hash. No production LIVE writes were made by the read-only corpus
trial. Synthetic regression freezes prove plumbing, not real predictive success.
