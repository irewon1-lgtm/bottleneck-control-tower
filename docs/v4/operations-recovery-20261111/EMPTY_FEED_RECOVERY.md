# Valid empty RSS/Atom classification

Task `BCT_V4_OPERATIONS_RECOVERY_20261111`. Development fix: `30d678757ce1da785b1387e2a841dbd99cbbc63a` (initial `7594788`, timezone-validation follow-up `30d6787`), based on `215997951c2956bd838b7415399a0a351ef80a62`. The pushed development ref was verified at the final commit. Main PR45 was not changed by this patch.

The preserved USGS Minerals response is valid empty RSS 2.0, rather than malformed source content. It was captured once at `2026-11-11T08:36:03.941956+00:00` from `https://www.usgs.gov/news/minerals/feed`: HTTP 200, `application/rss+xml; charset=utf-8`, 643 bytes. SHA256 `148ee2cbd14f29c4c40d809dfe336a200fc73a2297f1ed035e07e050a5473c0c` matches the unchanged saved capture and the earlier 2026-10-12 diagnosis. The committed metadata-only fixture preserves those exact bytes.

The document has one RSS2 channel, a title, valid link, present empty description, and zero items. The old common parser rejected every zero-entry feed with `MalformedRecord: feed has no entries`. The fix validates empty RSS2/Atom container metadata before returning an empty list. Existing nonempty entry validation is unchanged. Empty RSS2 requires a unique channel/title/link/description; empty description text is allowed. Empty Atom requires a unique title, absolute ID and valid timezone-bearing RFC3339 update time. HTML, DTDs, malformed XML, missing/duplicate required metadata, misplaced entries and malformed entries remain rejected. Bare legacy RDF containers remain rejected. No source-specific rule was added.

The existing collector/CLI now records a successful zero-record run: `status=succeeded`, `saved=updated=duplicates=failed=0`, `error=null`. This is logically **NO_NEW_INPUT**. The existing result contract has no separate detail field, so no database or receipt schema field was added and the error field was not repurposed. Tests verify that existing article rows survive and that no article is fabricated.

| Verification | Actual result |
|---|---|
| Saved actual capture + generic empty-feed tests before implementation | 7 failed, 32 passed; expected empty-input rejection reproduced |
| Initial related regressions | 77 passed |
| Additional review counterexamples: Atom timezone offsets `+02:99`, `+00:60`, `-00:60` | Three expected test failures reproduced before a strict offset-range fix |
| Final related regressions | **80 passed**, zero failures |
| Independent initial three-file review | 43 focused tests passed; no material findings; later timezone counterexample separately reproduced and fixed |
| Final-SHA repository CI / independent main PR | Parent-owned verification; not replaced with local results |

Final local command:

```bash
.venv/bin/python -m pytest -q tests/test_rss_empty_feed.py tests/test_rss_collector.py tests/test_rss_ai_workflow.py tests/test_rss_cycle_families.py tests/test_rss_state_workflow.py tests/test_v4_cross_industry.py
```

The owned commits contain only `src/bct/collectors/rss/collector.py`, `tests/test_rss_empty_feed.py` and the 643-byte `tests/fixtures/rss_empty_source.xml`. No new source request, AI/model call, production DB write, main merge or Gate execution occurred in this subtask. PROGRESS and the master REPORT were not edited.

**Minerals coverage remains unresolved:** the source still contains zero articles. Correcting its classification does not create articles, prove category coverage or authorize substituting the broader USGS All News feed. This preserves the distinction between valid empty intake and actual content recovery.

Machine-readable provenance and results: [EMPTY_FEED_RECOVERY.json](EMPTY_FEED_RECOVERY.json).
