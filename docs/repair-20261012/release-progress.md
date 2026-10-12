# BCT recovery checkpoint — 2026-10-13 00:05 KST

CLEAN PASS is **pending actual operating verification**.

- Released main: eab6b0e9ea823fb2b51bf70add4aa34d0a3a4a30, conditional non-forced update from cbe1f488db80f2232dd7ab99c598fe72ef55e41a.
- PR #38 merged; PR #37 was not merged again.
- Actual Gates 0–6: [38262053903](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38262053903), success.
- Gate artifact: 11754526906, sha256 0b0cbce86a844558a60c926d737ae0e7e40b6d4a8a5f123a3d185fc4a6299cf8. Downloaded bytes verified. Release guard: 228 code/test files match.
- Python 922 PASS / 1 prediction HOLDOUT SKIP; JavaScript 34 PASS; original 230-source regression/preservation PASS.
- Real isolated storage/CAS/interruption/rollback: [38256640428](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38256640428), PASS.
- Real isolated frozen REVIEW: [38257786983](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38257786983), 33 verified documents, 564 historical files unchanged.
- Main regression: [38267002079](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38267002079), success.
- Initial main Pages: [38267002090](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38267002090), success. This alone does not prove final candidate generation/UI/alerts.
- New main real RSS: [38267296051](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38267296051), collection success; 39 new articles, 3254 -> 3293, 117 of 125 feeds succeeded, 8 failed (2 MalformedRecord / 6 URLError).
- Earlier manual + scheduled RSS added 100; task-observed cumulative new RSS = 139.
- Main automatic candidate/native processing: [38267002062](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38267002062), in progress.
- Operating Stage 0 through FULL: [38267116728](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38267116728), in progress. Restored pinned 18 journals/receipts and cache inventory verified: source text 1672, evidence text 76, evidence raw 1070, source HTML 8, native claim files 27.
- Ops branch: a2a493867cec8f4cf05d085512c72c68b9f2280e; source code is the released main code, only the pinned recovery request differs.

Same real input packing measurement: peak Python allocation 239902509 -> 135514114 bytes (43.5% less), median 8.231 -> 8.222 seconds (time essentially unchanged). Same-input deterministic transport request count 14 -> 13. Original corpus remains archived; isolated verification artifact contains two receipts rather than another corpus copy (78831884 -> 4171 bytes).

Existing prior cleanup was audited, not repeated: 1951 obsolete shard paths; logical current-tree bytes 19274698532 -> 138393105. Git history remains intact; no claim of physical Git-pack reclamation. Our local generated build cleanup: 88 disposable generated files, 839948 bytes. No original articles, candidate history, failed records, judgments, live state or important backups removed.

Remaining: actual operating native completion including two archived stopped-owner timeout retries, normal main REVIEW_LEAD, exact candidate-generation Pages/UI/alerts verification, next actual scheduled execution, and required independent FULL cycles. Missing supply/TARGET/EARLY proof stays HOLD; prediction performance remains UNVERIFIED. No paid API, paid runner, force push or history rewrite.
