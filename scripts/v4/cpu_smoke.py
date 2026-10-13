"""Actual local CPU model smoke; SYNTHETIC, not forecast performance."""
import hashlib
import json
from pathlib import Path
import resource
import time

from bct.v4.adapters import CPUExtractor
from bct.v4.store import now

root = Path("var/v4/runtime")
text = "Atlas Metals produces tungsten in United States. Meridian signed new orders for tungsten in 2028."
doc = {"document_id": "synthetic-cpu-smoke", "body": text,
       "body_sha256": hashlib.sha256(text.encode()).hexdigest()}
extractor = CPUExtractor(root)
cpu = time.process_time()
wall = time.monotonic()
extractor.load()
load_cpu, load_wall = time.process_time()-cpu, time.monotonic()-wall
cpu = time.process_time()
wall = time.monotonic()
result = extractor.extract(doc)
assert any(s["label"] == "product" and "tungsten" in s["text"].lower() for s in result["spans"])
output = {"status": "PASS", "input_kind": "SYNTHETIC", "at": now(), "load_cpu_seconds": load_cpu,
          "load_wall_seconds": load_wall, "inference_cpu_seconds": time.process_time()-cpu,
          "inference_wall_seconds": time.monotonic()-wall,
          "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
          "result": result, "early": "BLOCKED"}
Path("var/v4/evidence/cpu-smoke.json").write_text(json.dumps(output, indent=2)+"\n")
print(json.dumps({k: v for k, v in output.items() if k != "result"}, indent=2))
