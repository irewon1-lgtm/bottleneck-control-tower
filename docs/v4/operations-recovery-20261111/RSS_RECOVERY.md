# RSS recovery — 2026-11-11

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`, P1; starting development code `42ee0a6ee6b0ed21228a0409aa64e973359bf65f`.

**Two of the previous fourteen failed feeds have verified official replacements. Twelve remain BLOCKED.** The patch changes only two URLs in `rss_feeds.yaml`; all 125 names/order and the previously working 111 feed URLs are unchanged. The collector and parser were not edited. This is source intake recovery, not evidence of independent forecast performance.

| Feed | Current original-URL observation, one attempt | Result |
|---|---|---|
| ESA Space News | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Launchers | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Navigation | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Space Engineering Technology | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Telecommunications Integrated Applications | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Space Science | HTTP 404 | BLOCKED; no proven category replacement |
| ESA Operations | HTTP 404 | BLOCKED; no proven category replacement |
| DOE Carbon Capture | Redirect to official HGEO category HTML, HTTP 200 | BLOCKED; category exposes no RSS link |
| USGS Minerals News | HTTP 200, valid RSS with zero entries | BLOCKED; no proven minerals-only replacement |
| DOE Fossil techlines | Redirect to named HGEO listing HTML, HTTP 200 | PASS; listing explicitly links verified XML feed |
| DOE Fossil clean coal news | Redirect to official category HTML, HTTP 200 | BLOCKED; category exposes no RSS link |
| DOE Fossil oil natural gas news | Redirect to official category HTML, HTTP 200 | BLOCKED; category exposes no RSS link |
| DOE Fossil petroleum reserves news | Redirect to official category HTML, HTTP 200 | BLOCKED; category exposes no RSS link |
| DOE Fossil blog | Redirect to named HGEO blog listing HTML, HTTP 200 | PASS; listing explicitly links verified XML feed |

The prior six DOE network errors now resolve to HTML rather than RSS. Their HTTP 200 responses do not establish functioning feeds; the unchanged parser correctly rejects the HTML. This separates the current URL/format failure from the previous transport failure.

The official relocation chains are:

| Preserved feed name | Original URL → official redirected listing | Explicit feed on that same listing |
|---|---|---|
| DOE Fossil techlines | `https://energy.gov/fe/techlines?view=rss` → `https://www.energy.gov/hgeo/listings/hgeo-press-releases-and-techlines?view=rss` | [HGEO Press Releases and Techlines](https://www.energy.gov/rss/hgeo/2282977) |
| DOE Fossil blog | `https://energy.gov/fe/blog?view=rss` → `https://www.energy.gov/hgeo/listings/hgeo-blog?view=rss` | [HGEO Blog](https://www.energy.gov/rss/hgeo/2283029) |

Each replacement returned HTTP 200, `application/rss+xml`, and ten entries accepted by the existing `parse_feed(payload, 10)`. The RSS channel title/link agree with the publisher's redirected category listing. Response SHA256s are `fd86f1f0e24daa55cab13624970862f0864f3531e572bedf2b02ae060dd46818` and `a7aa4e8bec465fe6b6684f2db1e2f100c2a1d420b47c33769f2f5ce488618c60`, respectively. The publisher-declared successors were used; the general HGEO feed was not substituted for the four narrower DOE categories.

ESA's actual [official RSS directory](https://www.esa.int/Services/RSS_Feeds) returned HTTP 200 and redirected to its new canonical article. It still advertises the old Space News/Launchers paths already observed returning 404. Current official operations and space-transportation pages expose no replacement RSS link. No new endpoint was guessed. For USGS, official search led to a working [All News feed](https://www.usgs.gov/news/all/feed), which was deliberately rejected because it broadens Minerals News. The empty minerals channel was not replaced with unrelated articles.

The fourteen configured originals were each requested once. Seven additional ESA/USGS discovery URLs and fourteen DOE discovery URLs were checked once each, including the two replacement XML feeds. These are 35 logical initial/discovery GET requests; automatic redirect transactions were not separately counted. No unchanged failed URL was retried. Source response bodies remain under `/tmp`; committed receipts contain transport metadata, hashes, URLs and the verified item dates rather than full source bodies.

| Verification | Actual result |
|---|---|
| Latest `data` snapshot downloaded read-only at commit `f1ea8b650a36388487efb8690b6c3a0635db1a0e` | SQLite SHA256 `116745656127534880b2253b175e3adad335ffd5a46b4d19d2e9c4da1e300dc7` matches remote `state.json`; integrity OK |
| Existing `RSSCollector` on a temporary copy, using the two captured real XML payloads | 9,921 → 9,941 articles; 20 saved, zero updated, zero first-pass duplicates |
| Same captured payloads through a second collector run, with no network request | Zero saved/updated; 20 duplicates |
| Stored source-date verification | All 20 item publication dates preserved exactly; not replaced with acquisition dates |
| Existing rows preserved in temporary copy | All 9,921 original article rows and nine existing AI-review rows unchanged |
| RSS collector/workflow/state regressions | 17 PASS, zero failures |
| Configuration preservation | 125 names/order preserved; only two failed URL values changed; working 111 URLs unchanged |
| Production database and source code | Zero production DB writes/uploads; parser/collector unchanged; schedules unchanged by this subtask |

Verification command:

```bash
.venv/bin/python -m pytest -q tests/test_rss_collector.py tests/test_rss_ai_workflow.py tests/test_rss_cycle_families.py tests/test_rss_state_workflow.py
```

The working 111 feeds were preserved without refetching them. This report does not claim a new complete 125-feed run or deployed success; those require the parent-controlled operational rollout and its actual run receipt. No new AI/model call or paid API was used. The twelve remaining feeds can resume only when a publisher-declared category RSS replacement is available, or the unchanged minerals channel returns real entries; no broad-category fallback is prepared.

Per-source timestamps, redirects, content types, hashes, collector outcomes, source dates and discovery receipts: [RSS_RECOVERY.json](RSS_RECOVERY.json).
