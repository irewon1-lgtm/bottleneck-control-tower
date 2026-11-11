# Extraction repair — consumed development evidence

Task: `BCT_V4_FULL_PIPELINE_DEBUG_20261111`; plan `BCT-V4-Q-1.0`, Q2 source/product binding. Start code: `23a0615f1a10f2b938cb2b5401706a1995b4d4f2`. This evidence supplements the existing execution plan and PROGRESS ledger.

The two extraction failures recorded in audit `2aaaa91f` reproduce on the starting code with the exact preserved article bodies. A generic repair now preserves both model identities and connects the explicit order-list parent to its new-equipment item. TARGET completeness and actual independent supply/demand pairs remain zero.

| Stage / condition | Execution | Result / evidence |
|---|---|---|
| Restore existing reading-quality snapshot to a temporary SQLite copy, open read-only, check integrity and all seven body hashes against stored hashes | New local execution | PASS; gzip SHA256 `49b3a551b4f68d6270aded7d1a9f1b3440bc34ea01159a234137c01f7c2b8b6a`, restored SQLite `a21227317a8d24225b54541e7a250138359b21793a64a19778db2abf3d0c4d29` |
| Reproduce the audit's exact FOX-XP and Sonoma statement offsets before changing production code | New local execution | PASS reproduction: FOX-XP unresolved, Sonoma reduced to `burn-in`; [extraction-before.json](extraction-before.json) |
| Test-first actual identity/list regressions | New local execution | Six expected failures and six passes before repair; actual failure reasons match the audit. Further ambiguity and adjective checks failed before their corresponding safeguards. |
| Preserve exact model identity and literal coordinates on the same statements | New local execution | PASS: FOX-XP `1049:1055`, Sonoma `894:900`; [extraction-after.json](extraction-after.json) |
| Preserve source-bound explicit list relationship and reject ambiguous/qualified list objects | New local execution | PASS in focused regressions; upgrades do not become new-equipment items; no inferred quantity, customer need date or qualified supply |
| Related extraction, collection, graph, adapter and product regressions | New local execution | 270 PASS, zero failures; command below |
| Objective Lock, original snapshot, existing development/evaluation gold and frozen HOLDOUT file integrity | New local execution | PASS byte-for-byte against baseline; [extraction-integrity.json](extraction-integrity.json) |
| Entire seven-document graph replay | New local execution by graph/linkage task | 60 retained events, 59 precursor events, zero complete TARGETs and zero independent pairs; [LINKAGE.json](LINKAGE.json) |

The fixed score denominator is **only the two already consumed, audited model-object statements**, identified by immutable body hashes and offsets before repair. A wrong selected object counts as both FP and FN. These are exact model-object binding scores, separate from historical AI/CPU product-exploration or event scores.

| Same actual development statements | TP | FP | FN |
|---|---:|---:|---:|
| Before | 0 | 1 | 2 |
| After | 2 | 0 | 0 |

The existing consumed six-document comparison was also rerun with the exact baseline reader from `23a0615f`, the current reader, unchanged historical partial windows, unchanged 25-target gold and the existing product scorer. Literal-product recognition is **TP1/FP4/FN24 before and TP1/FP4/FN24 after**: no change. The two repaired statements fall outside those historical partial windows. These literal candidates are separate from AI/CPU adopted-product scores; unmatched candidates are evaluator FP labels within this fixed gold scope, not newly independently adjudicated false products. See [extraction-development-six.json](extraction-development-six.json) and `extraction_development_replay.py`.

This small repair score does not establish corpus precision/recall, model improvement, independent accuracy or lead performance. Historical development/holdout scores and labels were not rewritten. No new HOLDOUT evaluation was run for tuning this repair.

`src/bct/precursor_scope_reader.py` version 5 adds a generic trademark-plus-contiguous-engineering-description recognizer, retaining the equipment descriptor as source evidence. Its compound-noun handling prevents a model and its own `test and burn-in system` description from becoming competing products. The purchase-object grammar understands `order includes` and stops before production-use clauses. A literal colon-list link is permitted only for a unique adjacent new-equipment item; unresolved/multiple new items remain held. Unknown adjacent item wording or identity invalidates uniqueness even when the product grammar recognizes no product; only an explicit equipment-description anaphor ends the list safely. Existing upgrade items are kept separate. Coordinated equipment stays unresolved, including comma coordination. Capitalized engineering adjectives and accounting/standards identifiers do not become newly recognized models. No issuer/model dictionary was added.

References remain bound to the unchanged document ID, body hash and literal offsets. Parent-list support records both parent and new-item coordinates; no text is rewritten. Quantity, delivery, commitment, qualified supply, independence and final selection gates retain their existing contracts. Customer silicon-photonics/AI-ASIC outputs are not selected as equipment orders. Existing adapter regressions additionally preserve actual/plan/negation, grants/financial-value rejection and purchase/output distinction.

Reproduce the same narrow score:

```bash
.venv/bin/python docs/v4/full-pipeline-debug-20261111/extraction_replay.py
```

Focused verification:

```bash
.venv/bin/python -m pytest -q tests/test_precursor_order_binding.py tests/test_precursor_target_gap.py tests/test_precursor_source_pipeline.py tests/test_v4_quote_followup.py tests/test_precursor_collection.py tests/test_precursor_evidence_graph.py tests/test_precursor_discovery.py tests/test_v4_quantitative_product.py tests/test_v4_repair.py
```

Independent review reproduced the serial-list/unknown-continuation failures before repair; the final integrated reviewer reran 106 relevant tests and found no remaining Important/Critical issues.

The parent task runs and reports the full repository suite and environment-related baseline failures separately. No new model installation, model inference, source retrieval or external AI request occurred here. No original SQLite/gzip, gold, HOLDOUT, PROGRESS or operating-state file was edited by this subtask. The final quality verdicts remain AI adoption FAIL, independent accuracy BLOCKED and lead performance BLOCKED. The two audited extraction defects and related local regressions meet their completion criteria; missing independent opposite-side supply evidence remains a separate blocker.
