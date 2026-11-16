# BCT V4 Session 6 — durable source-free research DB save/readback (2026-11-16 KST)

## Result

**PASS: isolated, immutable real GitHub research SQLite durable storage and independent remote readback.**

- [Completed verified run #43865173179](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43865173179). Parent artifacts #43857086796 and #43861667664 verified for successful run SHA, artifact ID and archive SHA-256 before combining.
- Research-only Git branch [`research/bct-s6-sourcefree-ledger-20261116`](https://github.com/irewon1-lgtm/bottleneck-control-tower/tree/research/bct-s6-sourcefree-ledger-20261116), published HEAD `0c15e7a0f94c1cfbcb4f6362bbbc5b5360106f65`.
- Durable SQLite: `research/bct-v4/s6-316-60-20261116/research-sourcefree.sqlite3` (761,856 bytes), SHA-256 `d0bef9da83910bf4ede638cea87df8f582bcb0cbb12033aee09aac64e832872d`.
- Remote byte-for-byte requery: `PASS_DURABLE_S6_RESEARCH_SQLITE_FRESH_READBACK`. SQLite integrity check and foreign-key check succeeded.
- GitHub Actions proof artifact ID `14224734405`, ZIP SHA-256 `b57248dd152984581d3c37bbc7d2b0964d53dcfa911e746a2500140cb93cfd5a`.
- A project-wide `*.sqlite3` Git ignore initially blocked the isolated research file. Fixed with **one explicit path-scoped `git add -f`**; production `canonical.sqlite3` and source sidecars remain untouched.

## Saved distinct tables and classification

| Research-only table | Rows | Meaning |
|---|---:|---|
| `article_intake` | 316 | Immutable hashed RSS-only IDs, do not claim previously failed acquisition |
| `source_reentry_plan` | 60 | Executed selected cohort membership and order |
| `source_attempts` | 60 | Genuine HTTP source reentry receipt; 24 FULL, 22 PARTIAL, 14 UNAVAILABLE |
| `target_holds` | 22 | All original 22 registered TARGETs remain HOLD |
| `research_facts` | 20 | Genuine official-public-document source-bound facts, Standard 12 + Centrus 5 + BWXT 3 |
| `source_bound_hints` | 147 | Article-version SHA and text span SHA hints, not economically independent physical pairs |

Exactly **18 of 60** public originals passed strict publisher + publication + body verification. These records' hashed references were joined against selected article IDs; no source HTML, article URL, quote text or transient private CPU cache is saved to this research SQLite.

**Verified and admitted independent demand/qualified available supply same-TARGET/year gap: 0 admitted.** This denotes absence of qualification within this scope, **not proof of no market bottleneck**. Previous published sector rank evidence 511 has **not** been reclassified or updated.

## Stage handoff and outstanding gates

**Session 6 scoped durable research DB: PASS. Session 6 whole evidence integration: PARTIAL.**

1. The remaining 316–60 = **256** previously RSS-only IDs require source access or evidence-based terminal HOLD and fresh status receipts; only IDs still absent in the latest sidecar should be fetched.
2. For the 18 strict original publications and 147 source-bound lead spans, independently verify issuer, specific product/specification, customer, region, quantity, period, unreserved eligible supply and counterevidence. Keep incomplete scope as HOLD.
3. Existing published operational sector rankings and protected STRICT/EARLY evidence gates must not be rewritten without a genuine qualified pair and repeatable source/DB validation.
4. Session 7 then validates public Pages displayed counts, derivation/refresh cadence and new-vs-historical evidence semantics. Session 8 runs real-input end-to-end checks including queue, persistence, fresh readback, and recovery.

## Safety and reproducibility

Only a new, isolated research branch was written by the successful workflow; normal `data`, `future-bottleneck-data`, `main` evidence records, `LIVE`, dashboard, RSS acquisition worker, and protected forecast engine were not mutated. Source-free records are subject to source SHA, payload SHA, SQLite integrity and uniqueness/foreign key checks. The publication uses explicit branch-sha CAS protection; a conflict aborts rather than silently overwriting existing data.

The work to date does **not** justify marking Session 6, 7 or 8 entirely PASS.
