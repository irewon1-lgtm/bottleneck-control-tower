# TARGET evidence acquisition

`python -m bct.target_acquisition` consumes an existing `targets-final.json`
export. It does not run RSS, screen the seed corpus again, modify canonical DBs,
create a LIVE session, or alter any discovery/EARLY/strict engine.

Each TARGET has separate DEMAND and SUPPLY requests. An existing screening
signal is retained as a lead, not treated as complete quantitative evidence.
If `existing_verified_facts` are supplied by role, only their missing fields are
requested. Complete sides are omitted. Original quotations, locators, raw
amounts and periods are preserved. Specification, region, supply pool, basis,
quantity/unit and explicit calendar bounds stay UNKNOWN unless stated.

```bash
PYTHONPATH=src .venv/bin/python -m bct.target_acquisition \
  --seed-targets /path/to/frozen/targets-final.json \
  --seed-documents /path/to/already-proven-source-documents.json \
  --direct-urls /path/to/missing-evidence-source-urls.json \
  --search-endpoint https://configured-public-search.example/search \
  --engine-manifest /path/to/pinned-engine-hashes.json \
  --live-store /path/to/existing/live/store \
  --output /path/to/new/immutable-operation
```

The optional search adapter accepts bounded RSS search responses or JSON
`{"results":[{"url":"https://original.example/document"}]}`. Search snippets
are discovery pointers only. No new service or credential is required by this
module. An endpoint must actually be reachable: missing or blocked search is
reported, never described as acquisition success. Previously completed request
and document files are read on resume; failures are not automatically retried.
A provider-wide CONNECT/HTTP refusal is grouped after the first failure, while
known direct URL requests continue. Separate operation directories are needed
for an explicitly authorized later retry.

Requests and downloads are batched at 100, with six download workers and bounded
20-second/4MB HTTPS captures. Captured raw HTML is retained by hash. Individual
failures do not abort the batch. No paywall bypass, proxy workaround, date
imputation, MW-to-mass conversion, or financial-to-physical conversion is used.
`reference_plan()` can add one hop to product-specific cited source documents;
pass previous attempted URLs and blocked domains to avoid repeated failures.

Provenance requires actual original URL/canonical identity, publisher and
attribution agreement, original publication evidence, acquisition time, and a
full accessible body with a reproducible hash. Conservative metadata failures
remain BLOCKED; saved original HTML is available for objective source-specific
review. A PASS article still does not establish an independent buyer/supplier
claim. Requoted claims remain unusable as strict signals until their original
source is verified. One ambiguous demand/supply sentence never becomes two
signals, and identical body hashes are deduplicated.

Only explicit scoped facts enter `discovery_document()` and the unchanged
strict validator. Period intersection narrows two actual calendar intervals
within an identical product/region/supply pool; the original periods remain
attached. A year or relative phrase is not converted to calendar bounds.
The frozen engine decides independence, physical comparability and possible
gaps. This preflight writes no LIVE state.

If preflight finds a candidate, the supplied engine hashes and existing session
must match before execution. The same candidate subset passes EARLY validation,
then `prospective.run(..., early=True)`, then strict `prospective.run()`.
Original JSON records and session bytes are checked for append-only retention.
The first strict result that stores a candidate stops that run. No session
creation path exists in this module. Performance validation is separate from
functional PASS.

The 2026-10-04 trial artifacts are in
`/workspace/bct-target-evidence-strategy-20261004/`. The final trial reports are
under `final/`. Failed search discovery prevented autonomous acquisition of all
missing independent primary-source evidence; no first strict PASS was claimed.
