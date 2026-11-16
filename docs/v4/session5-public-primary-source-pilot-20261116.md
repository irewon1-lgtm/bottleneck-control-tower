# BCT V4 — Session 5 public primary-source expansion pilot (2026-11-16 KST)

## Decision / stage

**Source acquisition: PASS (8 of 8 publicly prelisted official pages downloaded, recorded, and independently re-queried).**  
**Original-source attribution: 1 global strict provenance PASS + 7 separately verified visible publisher/title/date/fact attestations (strict provenance HOLD).**  
**Session 5 bottleneck qualification: PARTIAL. No qualifying demand > eligible supply pair has been demonstrated.**

Scope is a **research-only pilot** on the existing registered `unobligated-haleu-us-qualified-supply` TARGET. It **does not** claim that the original Session 4 consumer-news cohort (11 originals), the whole RSS database (~10k+ articles), protected STRICT/EARLY engines, private epoch, LIVE registered candidates, or public dashboard were newly processed or modified.

## Reproducible GitHub evidence

- First bounded live attempt, captured 6/8 sites, original 2 investor endpoints returned HTTP 403: [#43814726566](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43814726566).
- Approved issuer-site source URL substitution, all eight fetched with no HTTP failure: [#43815072751](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43815072751).
- Exact headline + adjacent published date + issuer marker + fact phrase validated separately for seven sites whose web publication metadata was insufficient for the unchanged strict parser: [#43815569496](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43815569496). The remaining one (Standard Nuclear) met the existing global strict original-provenance checks.
- Results are source-free code/status/counts/body SHA records and a SQLite file. Fresh independent process `PASS_S5_PUBLIC_ORIGINALS_FRESH_SQLITE_READBACK`, never HTML or quote payloads.

### Verified public primary sources (8 documents; 6 issuers)

| Organization | Exact public source | Research finding and limitation |
|---|---|---|
| Antares | [October 27: BWXT fabrication contract](https://antaresindustries.com/updates/bwxt-fuel-agreement) | Contract framework initial allocation 1 MTU; Antares says **two qualified TRISO fabrication sources**. This is not an approved claim of available, unreserved HALEU feed. |
| BWXT | [October 27: its own Antares contract announcement](https://www.bwxt.com/bwxt-announces-contract-with-antares-for-triso-nuclear-fuel-production/) | Independently published original corroborates the **same** Antares-BWXT initial 1 MTU agreement. Actual quantities, technical specifications, and schedules require subsequent task orders. **Do not count buyer+seller as two demand events.** |
| Antares | [November 6 roadmap](https://antaresindustries.com/updates/roadmap-update-jordan) | 2027 electrical reactor and 2028 deployment goals; goals are not a measured uranium/fuel annual requirement. |
| Standard Nuclear | [November 12 quarterly report](https://ir.standardnuclear.com/news-events/press-releases/detail/106/standard-nuclear-reports-third-quarter-and-year-to-date-2026-results) | Antares firm **1 MTU** and separately **optional up to 7 MTU** TRISO fuel. Also reports completed delivery of a Radiant reactor core. Optional and past deliveries must not be treated as future unreserved capacity. |
| Centrus | [September 17 Antares HALEU enrichment contract](https://www.centrusenergy.com/news/centrus-and-antares-sign-multi-year-haleu-supply-contract/) | Multi-year enrichment deal with deliveries before decade-end. Contract has no exact annual unreserved uranium quantity; upstream enrichment is not additive to finished TRISO fuel production. |
| Antares | [September 17 own announcement about Centrus](https://antaresindustries.com/updates/centrus-haleu) | Same economic agreement as Centrus release. Independent issuer websites **do not create independent causal demand facts**. |
| U.S. GAO | [August 20 GAO-26-107385](https://files.gao.gov/reports/GAO-26-107385/index.html) | Supply constraints may exist, but GAO reported no *then-current* national security mission mandating unobligated HALEU. Forecast evidence must distinguish national security from civilian fuel eligibility and its reference period. |
| U.S. DOE | [July 23 conditional allocation](https://stage.energy.gov/ne/articles/energy-department-distribute-third-round-haleu-nasa-and-radiant) | NASA/Radiant allocation announcement is **conditional**, not a proven delivered unreserved production stream. |

These observations are traceable to actual URL and body SHA, not the number of RSS headlines. Six distinct issuers does **not** mean six separate market supply facts or six qualified demand/supply pairs.

## Primary source qualification: strict versus bounded attestation

The unchanged global original verifier requires canonical identity, metadata publisher and attribution agreement, an explicit machine-readable publication timestamp, and a full parsed body. Seven of the captured official pages lacked one or more of those web metadata conditions even though the article text was accessible.

To prevent losing those leads without bypassing the strict engine, the isolated **research-only** pilot adds an alternate *visible primary-page attestation* requiring **all** of the following: fixed publicly verified HTTPS issuer URL, identical observed final URL, captured raw/body SHA, substantial body text, the exact article headline with its dated heading adjacent on the same page, explicit issuer marker, matched factual source phrase and no challenge page. It never changes the original `provenance=BLOCKED` judgement or increases eligibility for LIVE/strict candidate admission. Artificial titles, dates from other articles, missing issuers and tampered source hashes must fail.

## Actual causal independence and refutation findings

- Antares+BWXT reports: **one** initial fuel fabrication agreement (reported twice).
- Antares+Centrus reports: **one** upstream HALEU enrichment agreement (reported twice).
- Standard Nuclear contract: separate TRISO fabrication supplier agreement, but **1 MTU firm and 7 MTU optional** must not be merged with BWXT's own 1 MTU agreement as if unique final customer reactor demand; the supply qualification, shared reactor-fuel obligation, and allocation scope must be audited.
- Antares' two-source statement and the Radiant delivered core are material possible relief/counterevidence. They are not proof of sufficient same-scope supply in 2027–2029.
- GAO national security fuel obligation and DOE conditional allocation cannot be counted as firm exact same-customer supply without additional source.
- **Existing strict supply–demand engine was not run for this pilot.** Zero qualified pairs means **zero admitted/registered**, **not** a proven universe-wide null result.

## Remaining high-priority work / stage 5 gate

1. Obtain same-customer Antares firm purchase/order quantities by calendar year (not multiple press releases describing one contract), exact HALEU enrichment assay/form and TRISO fabrication qualification.
2. Obtain actual BWXT/Standard/Centrus **unreserved, accepted, eligible** output quantity with manufacturing/quality release periods, and the customer's corresponding needs within identical specs, region, time and units. `MTU HALEU feed` vs `MTU in completed TRISO fuel` cannot be silently summed or converted.
3. Reconcile alternative fabricators, DOE allocations, existing inventory, contract options, delivery relief and cancellation/delay evidence.
4. Run the existing protected strict graph/forecast validator only on independently verified same-scope original-source facts; retain all `UNKNOWN` fields. Re-open a candidate only with genuine independent DEMAND and eligible SUPPLY evidence and a demonstrated possible 12–36-month gap.
5. Continue full RSS corpus triage and publisher-origin original acquisition separately, prioritizing product/specification/time evidence over consumer product articles. This pilot by itself is not a production acquisition scheduler or a new rank score.

### Safety / provenance boundaries

Only these new files were added: `config/bct-s5-public-primary-pilot-20261116.json`, `tools/bct_s5_primary_originals_crosscheck.py`, `tests/test_bct_s5_primary_originals_crosscheck.py`, and `.github/workflows/bct-s5-public-primary-crosscheck.yml` plus this report. The public source list uses fixed article URLs, **no keyword queries made from private derivations**, no new paid APIs, no hidden scraping/proxy circumvention, no model call. Saved output contains only publisher names, verified public URLs, counts, codes, and source hashes; original article bodies are never uploaded. Production `main` acquisition, protected engines, private V4 research lineage, old S4 verification and user-facing dashboard remain unchanged.
