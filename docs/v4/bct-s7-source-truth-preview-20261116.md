# BCT V4 — Session 7 source-truth dashboard (read-only staging)

Date: 2026-11-16 KST. Scope: **prove meaningful and non-misleading dashboard evidence counts using real operating/historical research receipts**. This is an actual staged dashboard artifact, **not public Pages deployment**, and not overall Session 7 production PASS.

## Actual grounded result

[Real-source Actions run #43874148006](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43874148006) **SUCCESS**. Staged preview ZIP artifact ID **14229286689**, SHA-256 `284e085e00b14bbadb9b9aeaed750e0e2adb34f34731513ec550eea4e2f0f321`.

The workflow read **two independent sealed source-free research SQLites**, verified integrity + source and row hashes, then derived the dashboard status JSON. Both are real research artifacts, not invented counts:

- **Historically published 511 evidence records:** [Pages original 1,703 detail-file audit #43847161947](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43847161947), source-free artifact ID `14215199098`. Original live Pages artifact `14211394848` from run `43838794301`.
- **Current isolated research:** [durable research publication #43865173179](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43865173179), branch `research/bct-s6-sourcefree-ledger-20261116` at `0c15e7a0f94c1cfbcb4f6362bbbc5b5360106f65`, actual SQLite SHA-256 `d0bef9da83910bf4ede638cea87df8f582bcb0cbb12033aee09aac64e832872d`.

| Display category | Actual value | Source-time and evidentiary meaning |
|---|---:|---|
| Historical old published sector research records | **511** | **2026-10-14T23:16:13.592709+00:00**, not live shortage qualifications |
| Historical reviewed / structured / discovery | **23 / 211 / 277** | Sum 511, same historical unit |
| Historical sector-ranked / uncategorized | **508 / 3** | 508+3=511 |
| Published detailed JSONs | **1,703** | Different unit: includes 1,186 CPU products and 6 other reported, not 1,703 qualified pairs |
| Verified real original publications in new S6 pilot | **18** | Source publisher+publication time+original body, independent economic source pair not proven |
| Public original capture attempts in S6 pilot | **60** | 24 FULL / 22 PARTIAL / 14 UNAVAILABLE |
| Original source-bound research fact codes | **20** | Standard 12, Centrus 5, BWXT 3; leads, not eligible supply/demand pairs |
| Additional article sentence/locator research hints | **147** | Original body/hash location hints, **not added** to 511 |
| Registered TARGET unresolved review | **22 HOLD** | Prior historical FUTURE/EMERGING statuses are not fresh eligible gap certifications |
| Independently qualified comparable same-period demand-supply pairs newly admitted | **0** | Zero admitted in this evidence scope, **not evidence that no future shortage exists** |

The preview's **new `#research` tab** and the summary at the top of `#ranking` distinguish these categories, show the **actual old data date**, recorded Git source SHA prefixes and explicit HOLD/UNKNOWN state. Invalid, unavailable, tampered or falsely current `s7-research-status.json` fails closed with **"최신 연구 원장 미연결"**, rather than showing fake zero or promoting a historical count.

### Actual generated UI/source proof

1. The successful staging workflow verified the previous published Pages proof's original Actions run/head/artifact exact SHA-256 and freshly queried historical `published-511-sourcefree.sqlite3`.
2. It fetched the actual research branch commit and durable source-free SQLite, performed fresh SQLite readback and verified that the branch HEAD had not changed before finishing.
3. It created `s7-research-status.json` with the exact source generation timestamps separated from *the time the viewer checked*.
4. It ran the **real browser-side JS validator** on that **actual generated JSON**, plus pure adversarial tests and existing DOM-route tests; all passed in [#43874148006](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43874148006): **Python 4 PASS, JS 29 PASS / 0 FAIL**, file code syntax checked.
5. The published preview artifact includes only `index.html`, `style.css`, `view-model.js`, `app.js`, `s7-research-view.js`, and **the source-free verified status JSON**. No private original HTML, article body, internal API credentials or source article IDs.
6. The workflow has a **6-hour cron and manual trigger** configured for the default main branch following merge. This produces refreshed, read-only **preview artifacts**, not a public Pages deployment. The first post-merge scheduled execution has not yet been witnessed at the time of this report.

## No unsafe production implication

- **S7 source attribution + staging display:** PASS in the bounded research scope.
- **Production Pages update:** NOT_RUN, as the published Pages builder is bound to previously vetted `codex/bct-v4-integration` code and would otherwise mask new main research UI changes.
- **Operating research DATA integration:** separate stage 6 still PARTIAL; permanent source-free research ledger is saved and re-queried, but 256 unattempted article IDs and eligible physical pairs are outstanding.
- **Candidate ranking or portfolio recommendations:** none. Existing 511/historical FUTURE/EMERGING statuses are untouched, not relabeled by inference.
- **Session 8 automatic end-to-end operating verification:** NOT_RUN.

### Remaining Session 7 acceptance checks

1. Gate the actual **live Pages builder** to render this audited evidence count category separation using its own verified code generation path; do not silently change pinned approved deployment code.
2. Verify the first scheduled status regeneration after merge (automatic refresh) and the actual static HTML/browser rendering under production-equivalent server conditions.
3. Confirm new versus historical counts, stale-source protection and displayed timestamps against the **current** public data/sidecar generation and primary original facts, with no source hash drift.
4. When stage 6 qualifies any independent physical same-period pair, verify explicitly separate ranking admission and rerun production authorization tests before deployment.

**Outcome: `PASS_S7_SOURCE_TRUTH_DASHBOARD_PREVIEW_ONLY`; complete Session 7 public deployment & end-to-end operation PARTIAL.**
