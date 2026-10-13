"""Reproducible official-source functional trial, not an EARLY evaluation."""
import json
from pathlib import Path

from bct.v4.adapters import SourceClient
from bct.v4.pipeline import cycle
from bct.v4.store import Ledger

evidence = Path("var/v4/evidence")
evidence.mkdir(parents=True, exist_ok=True)
native = Ledger("var/v4/native-trial")
client = SourceClient()
urls = ["https://www.eia.gov/coal/production/quarterly/",
        "https://www.eia.gov/electricity/monthly/",
        "https://www.energy.gov/articles/fact-sheet-golden-era-american-nuclear-energy-has-arrived",
        "https://www.eia.gov/coal/production/quarterly/pdf/qcr.pdf"]
existing = {d["origin_url"] for d in native.latest_documents()}
for url in urls:
    if url not in existing:
        doc, raw, views = client.document(url)
        native.capture(doc, raw, views)
native.close()

config = {"urls": ["https://www.sec.gov/Archives/edgar/data/1701605/000170160526000023/bkr-20260630.htm",
                   "https://www.sec.gov/Archives/edgar/data/1701605/000119312526385823/d539011d8k.htm",
                   "https://www.energy.gov/articles/fact-sheet-golden-era-american-nuclear-energy-has-arrived"],
          "document_limit": 3, "ai_windows_per_document": 4}
result = cycle("var/v4/runtime", config)
(evidence / "actual-ai-final-cycle.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result.get(k) for k in ["integration_status", "live_captured", "failures", "readings",
                                            "cpu_seconds", "wall_seconds", "process_peak_rss_mib"]}, indent=2))
assert result["integration_status"] == "PASS", "actual-source integration did not pass"
assert len(result["readings"]) == 3 and all(r["ai_status"] == "PASS" for r in result["readings"])
