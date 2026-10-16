"""Smoke check the complete static dashboard before GitHub Pages publication."""
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "var/v4/pages-site")
manifest = json.loads((root / "build-manifest.json").read_text())
data = json.loads((root / "api/dashboard.json").read_text())
assert manifest["site_type"] == "PUBLIC_STATIC_READ_ONLY"
assert data["publication"]["code_commit"] == manifest["code_commit"]
assert data["publication"]["automatic_deployment"] == "GITHUB_PAGES_ACTIONS"
assert len(data["records"]) == data["counts"]["evidence"]
rows = list(data["records"]) + list(data.get("research_updates", {}).get("cpu_recovery", {}).get("records", []))
assert len(rows) == manifest["evidence_count"]
for row in rows:
    assert re.fullmatch("[a-f0-9]{64}", row["id"])
    detail = json.loads((root / "api/evidence" / (row["id"] + ".json")).read_text())
    assert detail["id"] == row["id"] and detail["all_references_verified"] is True
html = (root / "index.html").read_text()
js = (root / "app.js").read_text()
assert 'href="./style.css"' in html and 'src="./app.js"' in html
assert 'request("./api/dashboard.json")' in js
assert 'request(' + chr(96) + './api/evidence/' in js
assert '"/api/dashboard"' not in js
assert not (root / "canonical.sqlite3").exists()
assert not (root / ".env").exists()
print("PASS: public static V4:", manifest["evidence_count"], "verified details, commit", manifest["code_commit"])
