# Primary-source intake trial (shadow only)

`bct.shadow_sources_v2` is a separate bounded intake entry point. It reuses
read-only USAspending transport and the existing provenance verifier; it never
calls a collector that writes the production database or v1 prospective engine.
The existing `evaluate_pair_v2` pipeline consumes only validated original bodies.
Existing DATA_WAIT records, RSS sources, core engine hashes and LIVE stay intact.

The catalog registers SEC current 8-K filings, USAspending manufacturing awards,
Amkor official IR releases, Eaton official releases and EIA capacity analysis.
Provider indexes, RSS dates and contract search summaries remain leads. They are
not provenance proof, demand quantities or qualified supply. No amount/date is
inferred from award dollars or last-modified timestamps. No fabricated operator
identity is sent to SEC.

Run from the repository using the installed environment:

```bash
PYTHONPATH=src .venv/bin/python -m bct.shadow_sources_v2 \
  --catalog docs/v2-shadow-primary-sources.json \
  --output /workspace/bct-v2-primary-intake/new-attempt \
  --store /workspace/bct-v2-primary-intake/shadow-epoch \
  --completed-input /workspace/bct-v2-all-verified-batch-20261005/input.json
```

Use a new output directory for each attempt. Add `--completed-input` for each
already processed input snapshot. Original URLs are skipped before downloads;
body hashes deduplicate newly validated documents. Raw captures, checks, errors
and intake adapter hash are retained with the input. The shadow epoch records
its own immutable activation and unchanged core engine hashes. A shadow freeze
is never counted as LIVE performance. This is a bounded trial, not an enabled
production workflow.

Outstanding source-specific gates are explicit:

- SEC requires `BCT_SEC_USER_AGENT` containing the actual operator's reachable
  contact. Filings also need source-bound issuer/acceptance/primary-body proof;
  resolving a link or knowing the SEC hostname alone never promotes a filing.
- USAspending API search requires access to `api.usaspending.gov`. Award search
  summaries need full original contract/publication proof before promotion.
- An HTML release index with no eligible links (including client-rendered
  listings) records `SOURCE_INDEX_NO_ELIGIBLE_LINKS`.
- Missing canonical identity, publisher, publication or complete article body
  remains BLOCKED; a feed date does not fill a missing article publication date.

The actual 2026-10-05 trial validated two Amkor originals. SEC and USAspending
were blocked by missing contact and CONNECT 403 respectively. EIA bodies were
captured but did not pass the existing provenance gate. Eaton's index had no
eligible article links. The two validated originals produced seven events and
zero independent cross-document pairs/EARLY candidates. No success is claimed
for the blocked providers.
