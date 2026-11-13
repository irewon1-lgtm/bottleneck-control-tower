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
from bct.v4.sector_ranking import ranks
assert data.get("sector_rankings") == ranks(data["records"])
prior = data.get("sector_rank_previous", {})
assert prior.get("status") in ("VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT",
                              "PREVIOUS_PUBLIC_SNAPSHOT_UNAVAILABLE",
                              "PREVIOUS_PUBLIC_NOT_QUERIED_OUTSIDE_PAGES")
if prior.get("status") == "VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT":
    assert len(prior["source_dashboard_sha256"]) == 64
    assert all(x["rank"] > 0 for x in prior["ranks"].values())
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
if data.get('operating_research'):
    from bct.v4.public_research import validate_snapshot
    public = validate_snapshot(json.loads((root / 'api/research.json').read_text()))
    assert public == data['operating_research']
    assert manifest['research_generation'] == public['generation']
    assert manifest['research_snapshot_sha256'] == public['snapshot_sha256']
    assert data['data_at'] == (public['clocks']['data_at'] or data['historical_data_at'])
# The manual source-acquisition public receipt remains independently bound.
source_capture = data.get("latest_source_capture", {})
if manifest.get("source_intake_sha256"):
    import hashlib
    raw = (root / "api/source-intake.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["source_intake_sha256"]
    source = json.loads(raw)
    assert source == source_capture and source["status"] == "VERIFIED_PUBLIC_SOURCE_INTAKE"
    assert source["source_run_id"] == manifest["source_intake_run_id"]
    assert source["rss_run_id"] <= manifest["rss_source_run_id"]
    assert source["captured"] + source["held"] == source["seed_attempts"]
    assert source["classification"] == "CAPTURED_SOURCE_DOCUMENTS_NOT_VERIFIED_BOTTLENECKS"
else:
    assert source_capture.get("status") == "NOT_VERIFIED_OFFLINE"
    assert not (root / "api/source-intake.json").exists()
if __import__("os").environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages":
    assert manifest.get("source_intake_sha256")
# The canonical data-branch source ledger has separate provenance receipts.
registered=data.get("registered_precursor_original_research")
assert isinstance(registered,dict)
if manifest.get("registered_source_research_sha256"):
    import hashlib
    raw=(root/"api/registered-source-research.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest["registered_source_research_sha256"]
    saved=json.loads(raw)
    assert saved==registered
    assert saved["status"]=="VERIFIED_PERSISTED_ORIGINAL_SOURCE_RESEARCH"
    assert saved["verified_original_record_count"]==len(saved["records"])
    assert saved["rss_run_id"]==manifest["rss_source_run_id"]
    assert saved["data_commit"]==manifest["rss_data_ref"]
    assert manifest["registered_source_research_count"]<=len(saved["records"])
    assert all(r["verification"]=="ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED"
        and not r["confirmed_future_shortage"] for r in saved["records"])
    indexed={r["id"] for r in data["rss_research_evidence"]["source_records"]}
    assert {r["id"] for r in saved["records"]} <= indexed
else:
    assert registered["status"]=="NOT_QUERIED_OFFLINE"
    assert not (root/"api/registered-source-research.json").exists()
# Dynamic verified RSS research observations are registered separately from
# the historic 511 records. Screened headlines and incomplete original proofs
# must not become sector evidence or independent demand/supply gaps.
rss_reg=data.get("rss_research_evidence")
live=data.get("sector_rankings_live")
assert isinstance(rss_reg,dict) and isinstance(live,dict)
assert rss_reg["format"]=="bct-rss-sector-evidence-register-1"
assert live["count_kind"]=="HISTORICAL_RESEARCH_PLUS_ORIGINAL_VERIFIED_UNPAIRED_OBSERVATIONS"
assert live["historical_source_rows"]==data["sector_rankings"]["ranked_record_count"]
assert live["new_original_verified"]==rss_reg["source_verified_sector_count"]==len(rss_reg["source_records"])
assert live["ranked_record_count"]==live["historical_source_rows"]+live["new_original_verified"]
assert all(r["category"]=="rss_source_observation" and r["verification"]=="ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED"
           and r["confirmed_future_shortage"] is False
           and re.fullmatch("[0-9a-f]{64}",r["body_sha256"])
           for r in rss_reg["source_records"])
assert live["no_verified_supply_shortage_promoted"] is True
assert __import__("hashlib").sha256((json.dumps(rss_reg,ensure_ascii=False,allow_nan=False,separators=(",",":"))+chr(10)).encode()).hexdigest()==manifest["rss_research_sha256"]
assert manifest["rss_research_verified_source_records"]==len(rss_reg["source_records"])
if __import__("os").environ.get("GITHUB_WORKFLOW")=="Read-only BCT Pages":
    assert rss_reg["status"]=="SOURCE_BOUND_RESEARCH_BRIDGE"
    assert rss_reg["sidecar_commit"]==manifest["rss_research_sidecar_commit"]
else:
    assert rss_reg["status"]=="OFFLINE_NOT_QUERIED"
# Article screening and an immutable full-RSS audit never change the ranked
# evidence ledger. The live sidecar manifest index is NOT verified body provenance.
funnel=data.get("source_backlog")
assert isinstance(funnel,dict) and funnel.get("format")=="bct-source-and-screening-funnel-1"
assert funnel["classification"]=="NOT_VERIFIED_BOTTLENECK_EVIDENCE"
assert funnel["rank_input_not_increased_by_rss"] is True
assert funnel["historical_rank_input_count"]==len(data["records"])
audit=funnel["pinned_audit"]
assert sum(audit["body_counts"].values())==audit["rss_articles"]
assert audit["sidecar_results"]+audit["unlinked"]==audit["rss_articles"]
assert audit["selected_future_work"]["completed_in_this_audit"]==0
assert 'function sourceBacklogPanel()' in js
assert __import__("hashlib").sha256((json.dumps(funnel,ensure_ascii=False,allow_nan=False,separators=(",",":"))+chr(10)).encode()).hexdigest()==manifest["screening_funnel_sha256"]
if __import__("os").environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages":
    assert funnel["status"]=="VERIFIED_LIVE_INDEX_AND_PINNED_AUDIT"
    assert manifest["screening_sidecar_commit"]==funnel["live_sidecar"]["sidecar_commit"]
else:
    assert funnel["status"]=="OFFLINE_PINNED_AUDIT_ONLY"
    assert manifest["screening_sidecar_commit"] is None
assert data["sector_rankings"]==ranks(data["records"])
# Separate RSS NEWS metadata never counts as vetted forecast evidence.
rss_summary = data.get("rss_news_summary")
assert isinstance(rss_summary, dict)
if manifest.get("rss_news_sha256"):
    import hashlib
    raw_news = (root / "api/rss-news.json").read_bytes()
    assert hashlib.sha256(raw_news).hexdigest() == manifest["rss_news_sha256"]
    rss = json.loads(raw_news)
    assert rss["format"] == "bct-public-rss-news-1"
    assert rss["status"] == "VERIFIED_PUBLIC_RSS_METADATA"
    assert rss_summary["status"] == rss["status"]
    assert rss_summary["source_run_id"] == manifest["rss_source_run_id"]
    assert len(rss["articles"]) == manifest["rss_article_count"] == rss_summary["visible_article_count"]
    assert len([r for r in rss["articles"] if r["is_new"]]) == rss["new_article_count"]
    assert rss["feed_failed"] == len(rss["failed_feeds"])
    assert rss["classification"] == "RSS_TITLE_METADATA_NOT_VERIFIED_BOTTLENECK"
    assert all(set(r) == {"id", "source", "source_group", "title", "url", "published_at", "publication_date_status",
                          "collected_at", "snippet", "is_new", "link_available"} for r in rss["articles"])
    assert data["sector_rankings"] == ranks(data["records"])  # RSS adds no ranking signal.
else:
    assert rss_summary["status"] == "NOT_LOADED_OFFLINE"
    assert not (root / "api/rss-news.json").exists()
if __import__("os").environ.get("GITHUB_WORKFLOW") == "Read-only BCT Pages":
    assert manifest["rss_news_sha256"] and rss_summary["status"] == "VERIFIED_PUBLIC_RSS_METADATA"
print("PASS: public static V4:", manifest["evidence_count"], "verified details, commit", manifest["code_commit"])
