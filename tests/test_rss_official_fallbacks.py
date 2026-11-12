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
    assert len(feeds)==116  # 115 validated active feeds plus one ESA NAVISP programme Atom feed
    assert feeds["ESA Space News"]=="https://www.esa.int/rss/news.rss"
    assert feeds["ESA NAVISP Navigation News"]=="https://navisp.esa.int/atom/latest-news"
    assert "ESA Navigation" not in feeds  # Narrow NAVISP feed is not full navigation news
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


def test_navisp_atom_is_programme_specific_and_parseable_with_existing_collector():
    from bct.collectors.rss.collector import parse_feed

    atom = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <title>ESA NAVISP News</title>
      <entry>
        <title>PNT technology update</title>
        <link rel="alternate" type="text/html"
              href="https://navisp.esa.int/news/article/example-programme-update" />
        <published>2026-11-12T11:05:11+00:00</published>
        <summary type="html">&lt;p&gt;NAVISP programme update.&lt;/p&gt;</summary>
      </entry>
    </feed>'''
    entries = parse_feed(atom, limit=10)
    assert len(entries) == 1
    assert entries[0].source == "navisp.esa.int"
    assert entries[0].url == "https://navisp.esa.int/news/article/example-programme-update"
    assert entries[0].published_at == "2026-11-12T11:05:11+00:00"
    assert entries[0].snippet == "NAVISP programme update."
