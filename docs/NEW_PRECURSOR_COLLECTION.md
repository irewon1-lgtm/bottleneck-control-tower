# New-only precursor collection

The existing 2,000-document corpus is closed. Its ID/URL-only exclusion manifest
is `config/precursor-baseline-exclusions.json`; no original body or screening
export is loaded by this collector. Existing LIVE session, Objective Lock,
precursor discovery, EARLY, strict and S3 implementations are unchanged.

`rss-live-check.yml` exports a before/after ID delta and actual collection times.
The new `precursor-acquisition.yml` consumes that delta after successful main
RSS runs. It does not repeat a baseline acquisition or modify the canonical DB.
The first delta establishes a collector cutover, not a new LIVE session.

Each new accessible original is verified with existing canonical/publisher,
publication precision, acquisition, body/hash/version checks. RSS publication
values never become original publication metadata. Source paragraphs and exact
field locators are preserved. Both ordinary explicit assertions (`product is`,
`grade is`, `market is`, `customers are`, `qualified suppliers are`) and labelled
fields are supported. The existing open precursor noun-phrase recognizer can
supply a literal product anchor for targeted queries. Scope cannot be inferred
from a publisher address, URL, search query, pronoun or a convenient year.
Ambiguous or absent attributes remain UNKNOWN. This does not constitute a
universal natural-language scope resolver.

Events immediately retain product, specification, region, customer group,
qualified supply pool and a source-backed future window or UNKNOWN. Coarse
calendar bounds retain `SOURCE_WINDOW_NOT_EXACT_NEED_DATE`; exact/relative raw
periods unsupported by the unchanged engine remain references, not invented
calendar periods. Requoted third-party claims are leads for original-source
acquisition; they are excluded from direct independent-pair validation.

Per scope, only missing DEMAND/SUPPLY or incomplete-side evidence is requested.
Queries use literal observed fields and ask for quantities and delivery/ramp
periods. Missing product prevents an unbounded query. Product-specific citations
are followed one hop to a different host; same-host links do not fabricate
independence. The existing bounded RSS/JSON search adapter defaults to the free
Bing RSS endpoint; `BCT_PRECURSOR_SEARCH_ENDPOINT` can select a reachable compatible
endpoint. Search results are URL pointers only. CONNECT and site HTTP refusal
are distinct, grouped after provider refusal and retained without repeated
failed-URL attempts. No paid API or alternate proxy is introduced.

New seeds are processed in batches of 100 with six body-fetch workers. URL and
body versions deduplicate before independence. Original documents, raw hashes,
events, requests, blocked reasons and cycle results accumulate in a separate
private collector store using atomic create-if-absent files and an operation
lock. A missing search provider leaves a durable pending request. The engines
only see successfully verified new original versions.

The existing synthesizer and EARLY engine decide compatibility, independence,
future tension and refutation. This collector additionally requires the actual
candidate's demand and supply windows to overlap before LIVE freeze. Quantities
remain UNKNOWN when missing. Explicit shortage material remains confirmation.
No strict execution or S3 promotion is performed by this collector.

The workflow restores the existing `live-state` branch byte for byte at its
original `/workspace/bct-live-state` path, preserving session-bound feed paths.
It never invokes session creation. Only eligible new EARLY records reach
`prospective.run(..., early=True)`. Prior JSON bytes are checked afterward.
New LIVE JSON files alone are appended to `live-state` with a branch-head check;
existing files are not staged. The data branch gets only aggregate
`precursor-index.json`, preserving canonical blobs with a separate Git index.

Private full source state is handed to the next cycle using the existing GitHub
Actions artifact mechanism, retained for 30 days. If the indexed artifact is
missing, restoration fails closed: it does not reset the collector or reopen
old corpus. This retention is a concrete durability limit, not permanent
storage. Original first records use the existing permanent LIVE state path.

Local execution against newly collected rows:

```bash
PYTHONPATH=src .venv/bin/python -m bct.precursor_collection \
  --manifest /path/to/new-document-manifest.json \
  --state /path/to/new-only-private-state \
  --live-store /workspace/bct-live-state/live-state/bct-live-20261004T120019Z-e74254ee4bca/store
```

A manifest has `collection_started_at`, `preexisting_document_ids`,
`preexisting_urls`, and `documents` with `document_id`, `url`, `collected_at`.
For more than 100 new rows use `.github/scripts/new_precursor_cycle.py`, which
processes successive batches. Omitting LIVE store permits acquisition/preflight
only and reports pending candidates without claiming an actual freeze.

Functional tests use fresh synthetic source HTML and an isolated fixture store.
Their positive result proves source acquisition -> scope -> independent pair ->
common window -> synthesized TARGET -> immutable EARLY first plumbing. It does
not establish a real predictive result. Actual new-source checks and freezes
must be reported separately. Workflow edits require normal code publication to
main before scheduled GitHub execution; local tests are not a deployment claim.
