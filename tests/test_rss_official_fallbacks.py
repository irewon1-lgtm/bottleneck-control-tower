"""Only verified official replacement RSS endpoints remain active.

These are current configuration repairs, not a claim that ESA/DOE specialty
feeds or all HTTP connection failures were restored. Historical DB is unchanged.
"""
from pathlib import Path
import yaml
from bct.collectors.rss.cli import load_feeds

ROOT=Path(__file__).resolve().parents[1]

def test_official_broad_feeds_replace_dead_legacy_endpoints():
    path=ROOT/"rss_feeds.yaml"
    raw=path.read_text(encoding="utf-8")
    feeds=load_feeds(path)
    assert len(feeds)==115  # 125 before: 10 dead specialty streams retired; one ESA general replacement
    assert feeds["ESA Space News"]=="https://www.esa.int/rss/news.rss"
    assert feeds["DOE Fossil techlines"]=="https://www.energy.gov/rss/hgeo/2282977"
    assert any("ESA Human Spaceflight"==name for name in feeds)  # Previously working specialty preserved.
    assert any("DOE Fossil blog"==name for name in feeds)
    assert not any("energy.gov/fe/" in url for url in feeds.values())
    assert not any("/rssfeed/Our_Activities/Space_News" in url for url in feeds.values())
    assert "category-specific coverage" not in raw  # Intent communicated as specialist feed not restored.
    assert "retired pending a verified specialist feed" in raw

def test_all_active_rss_feed_urls_are_https_with_finite_names():
    feeds=load_feeds(ROOT/"rss_feeds.yaml")
    assert len(feeds)==len(set(feeds.keys()))
    assert all(url.startswith("https://") and len(name)<150 for name,url in feeds.items())
