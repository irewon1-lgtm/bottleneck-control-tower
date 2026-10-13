"""Selected native-input parser benchmark; no invented full-corpus accuracy."""
import json
from pathlib import Path
import resource
import time

from bct.v4.adapters import html_views
from bct.v4.store import Ledger, now

# These six physical quantities come from the pre-existing research EIA
# observations, not a new extraction-selected gold. All must exist in raw HTML.
anchors = ["125.4", "61.6", "26.8", "0.7", "98.8", "118.3"]
ledger = Ledger("var/v4/native-trial")
doc = next(d for d in ledger.latest_documents() if d["origin_url"] == "https://www.eia.gov/coal/production/quarterly/")
raw = ledger.db.execute("SELECT data FROM blobs WHERE id=?", (doc["raw_sha256"],)).fetchone()[0]
assert all(value in raw.decode() for value in anchors)
rows = []
for repeat in range(5):
    views = html_views(raw)
    rows.append({"repeat": repeat + 1, "cpu_seconds": views["cpu_seconds"],
                 "baseline_chars": len(views["baseline"]["body"]),
                 "trafilatura_chars": len(views["trafilatura"]),
                 "baseline_anchors_retained": sum(a in views["baseline"]["body"] for a in anchors),
                 "trafilatura_anchors_retained": sum(a in views["trafilatura"] for a in anchors)})
output = {"at": now(), "status": "PASS", "input_kind": "REAL_NATIVE_HTML",
          "url": doc["origin_url"], "raw_sha256": doc["raw_sha256"], "bytes": len(raw),
          "anchors": anchors, "rows": rows,
          "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
          "full_text_recall": "UNKNOWN", "target_role_accuracy": "UNKNOWN",
          "limits": "One document, six selected numeric anchors, cumulative process RSS, no per-parser RAM attribution"}
assert all(r["baseline_anchors_retained"] == r["trafilatura_anchors_retained"] == len(anchors) for r in rows)
Path("var/v4/evidence/native-parser-benchmark.json").write_text(json.dumps(output,indent=2)+"\n")
ledger.close()
print(json.dumps(output, indent=2))
