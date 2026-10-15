"""HTTPS verification. Service credential arrives only through hidden stdin."""
import json
from pathlib import Path
import sys
import termios
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


settings = termios.tcgetattr(sys.stdin)
settings[3] &= ~termios.ECHO
termios.tcsetattr(sys.stdin, termios.TCSANOW, settings)
print("Ready for verification JSON on stdin (input is hidden).", flush=True)
args = json.loads(sys.stdin.readline())
opener = build_opener(NoRedirect)
origin = args["origin"]
if origin != "https://bct-v4-dashboard.ire-won1.chatgpt.site":
    raise ValueError("Unexpected destination")


def get(path, auth=True):
    headers = {"OAI-Sites-Authorization": "Bearer " + args["token"]} if auth else {}
    try:
        r = opener.open(Request(origin + path, headers=headers), timeout=30)
    except HTTPError as exc:
        r = exc
    return r.code, dict(r.headers), r.read()


status, headers, body = get("/api/dashboard")
assert status == 200, status
d = json.loads(body)
report = {"origin": origin, "counts": d["counts"], "data_at": d["data_at"],
          "publication": d.get("publication"), "tests": []}
if args.get("expected_commit"):
    assert d["publication"]["code_commit"] == args["expected_commit"]
    assert d["counts"]["body_nonempty"] == 235 and d["counts"]["pending"] == 2
    assert d["counts"]["evidence"] == 511
    assert d["counts"]["future_candidates"] == {"S1": 0, "S2": 0, "S3": 0}
    recovery = d["research_updates"]["cpu_recovery"]
    assert recovery["summary"]["CPU_product_proposals_retained"] == 1186
    assert recovery["summary"]["new_source_reported_actual_event_reviews"] == 6
    assert len(recovery["records"]) == 1192
    for category in ("cpu_product", "reported"):
        row = next(r for r in recovery["records"] if r["category"] == category)
        code, h, b = get("/api/evidence/" + row["id"])
        detail = json.loads(b)
        assert code == 200 and detail["all_references_verified"] and detail["stage"] == "UNKNOWN"
        report["tests"].append({"test": category + " original quote endpoint", "result": "PASS"})
    code, h, b = get("/api/export")
    assert code == 200 and "attachment" in h.get("Content-Disposition", "")
    assert json.loads(b) == d
    report["tests"].append({"test": "download matches latest saved research", "result": "PASS"})
    for path in ("/", "/api/dashboard", "/api/export", "/api/evidence/" + recovery["records"][0]["id"]):
        code, h, b = get(path, False)
        assert code in (301, 302, 303, 307, 308, 401, 403)
        assert b'"counts"' not in b
        report["tests"].append({"test": "anonymous blocked " + path, "result": "PASS", "http": code})
    for path in ("/.env", "/worker/index.js", "/docs/v4/cpu-recovery/research-snapshot.sqlite3.gz"):
        code, h, b = get(path)
        assert code == 404
        report["tests"].append({"test": "source excluded " + path, "result": "PASS", "http": code})
if args.get("output"):
    Path(args["output"]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False), flush=True)
