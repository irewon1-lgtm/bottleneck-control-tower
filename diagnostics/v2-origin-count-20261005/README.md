# Reproduce the sealed single diagnostic

Branch: `codex/v2-origin-count-diagnostic-20261005`.
Original-preservation commit: `4ad92a8`.
Diagnostic code/input-review seal commit: `c2f072e`.

Read `AUDIT.md`, `manifest.json`, `diagnostic-seal.json`, then
`results/validity-and-summary.json` and `results/item-table.json`.
`results/item-table.md` is a compact per-relation view; full gate states, source
locations, T uncertainty and unchanged A/B decisions are in the JSON table.
The gzip archives decompress byte-for-byte to the original immutable receipt,
CLI presentation and original source HTML; original and compressed hashes are
stored separately. No public-network request is needed to inspect or replay.

Minimum isolation checks (synthetic; no real-corpus A/B rerun):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest diagnostics/v2-origin-count-20261005/test_diagnosis.py -q -p no:cacheprovider
```

The actual comparison command executed once at the sealed code commit was:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python diagnostics/v2-origin-count-20261005/run_diagnosis.py --output diagnostics/v2-origin-count-20261005/results
```

The existing output directory intentionally prevents a second run. Verification
of saved results is read-only; do not rerun to tune results. A future explicitly
requested reproduction can use a distinct output directory on the same sealed
input/rules; it would be a separately labelled reproduction, not a second
comparison claimed in this diagnostic.

Dependencies are in the preserved `pyproject.toml`; tested with the existing
workspace Python/pytest. Evaluation uses no AI reader and no live services.
Inspect source code or dependencies only in the preserved version. The frozen
engine hashes are validated before any evaluation. A baseline mismatch, hash or
input change writes `INVALID.json` and terminates. No invalid actual run occurred.

All outputs are BACKFILL diagnostics. No LIVE freeze, strict engine run, v1
comparison, deployment, PR, merge or operating schedule change is performed.
T and T_scope are UNKNOWN, not manufactured dates.
