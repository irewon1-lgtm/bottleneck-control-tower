import json

from bct.models import RadarItem
from bct.radar_signals import build, extract


def test_headline_and_description_only_and_conservative_terms():
    assert extract("Transformer lead times remain elevated", None) == [
        {"signal": "LEAD_TIME", "candidate_term": "transformer"}]
    assert extract("Pentagon to nearly double AMRAAM production", "Nothing else") == [
        {"signal": "CAPACITY_EXPANSION", "candidate_term": "AMRAAM"}]
    assert extract("News", "Shortage of transformers; qualification delay") == [
        {"signal": "QUALIFICATION_DELAY", "candidate_term": None},
        {"signal": "SHORTAGE", "candidate_term": "transformers"}]
    assert extract("Lead time", "Lead time") == [
        {"signal": "LEAD_TIME", "candidate_term": None}]
    assert extract("Capacity expansion announced", "Rising price alone") == [
        {"signal": "CAPACITY_EXPANSION", "candidate_term": None}]


def test_phrase_variants_normalize_to_original_eight_signals():
    examples = {
        "SHORTAGE": ["Transformer shortfall", "Tight supply of transformers"],
        "LEAD_TIME": ["Transformer delivery times rise"],
        "CAPACITY_CONSTRAINT": ["Transformer bottleneck", "Transformer capacity constrained"],
        "UNABLE_TO_MEET_DEMAND": ["Transformer demand exceeds supply", "Transformers cannot meet demand"],
        "BACKLOG_INCREASE": ["Transformer record backlog", "Transformer backlog growth"],
        "PRODUCTION_DELAY": ["Transformer delivery delays"],
        "QUALIFICATION_DELAY": ["Transformer certification delay"],
        "CAPACITY_EXPANSION": ["New plant for transformers", "Transformer ramp production",
                               "Double AIM-120 production", "Double AMRAAM production"],
    }
    for signal, headlines in examples.items():
        for headline in headlines:
            assert {found["signal"] for found in extract(headline, None)} == {signal}, headline
    assert extract("Double AIM-120 production", None) == [
        {"signal": "CAPACITY_EXPANSION", "candidate_term": "AMRAAM"}]
    assert extract("Double AMRAAM production", None) == extract("Double AIM-120 production", None)


def test_rebuild_idempotent_updates_and_recomputes_without_touching_source(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        db.add(RadarItem(id="rss-1", source="news.example.org", external_id="one",
                         title="Transformer lead times remain elevated", url="https://news.example.org/1",
                         snippet="Transformer lead times remain elevated", source_type="NEWS"))
        db.add(RadarItem(id="other-1", source="other.example.org", external_id="two",
                         title="Solar shortage", url="https://other.example.org/2", source_type="NEWS"))
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  news: https://news.example.org/feed.xml\n")
    first = build(settings, feeds)
    assert (first["processed"], first["matched_articles"], first["new_signals"]) == (1, 1, 1)
    snapshot = (settings.derived_dir / "rss_signals.json").read_bytes()
    second = build(settings, feeds)
    assert second["existing_duplicates"] == 1 and second["new_signals"] == 0
    assert (settings.derived_dir / "rss_signals.json").read_bytes() == snapshot
    with sf.begin() as db:
        item = db.get(RadarItem, "rss-1")
        item.title = "Transformer production delay"
        item.snippet = ""
        item.updated_at = "2026-09-30T00:00:00+00:00"
    third = build(settings, feeds)
    assert (third["new_signals"], third["removed_signals"]) == (1, 1)
    entries = json.loads((settings.derived_dir / "rss_signals.json").read_text())["entries"]
    assert len(entries) == 1 and entries[0]["signals"] == [
        {"signal": "PRODUCTION_DELAY", "candidate_term": "transformer"}]
    with sf() as db:
        assert db.get(RadarItem, "rss-1").title == "Transformer production delay"


def test_candidate_summary_counts_distinct_articles_and_sources(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        for id_, host, title, published in (
            ("one", "first.example.org", "AMRAAM shortage and AMRAAM shortage", "2026-09-01T00:00:00+00:00"),
            ("two", "second.example.org", "Double AIM-120 production", "2026-09-02T00:00:00+00:00"),
            ("three", "first.example.org", "Transformer lead time", "2026-09-03T00:00:00+00:00"),
        ):
            db.add(RadarItem(id=id_, source=host, external_id=id_, title=title,
                             url=f"https://{host}/{id_}", published_at=published, source_type="NEWS"))
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  first: https://first.example.org/feed\n"
                     "  second: https://second.example.org/feed\n")
    result = build(settings, feeds)
    assert (result["processed"], result["matched_articles"]) == (3, 3)
    by_name = {item["candidate_term"]: item for item in result["candidates"]}
    assert by_name["AMRAAM"] == {"candidate_term": "AMRAAM", "article_count": 2,
                                 "signals": ["CAPACITY_EXPANSION", "SHORTAGE"], "source_count": 2,
                                 "latest_at": "2026-09-02T00:00:00+00:00", "status": "WATCH"}
    assert by_name["transformer"]["status"] == "OBSERVE"
    again = build(settings, feeds)
    assert again["new_signals"] == 0 and again["candidates"] == result["candidates"]


def test_bad_feeds_config_does_not_replace_prior_output(setup, tmp_path):
    settings, sf = setup
    valid = tmp_path / "valid.yaml"
    valid.write_text("feeds:\n  news: https://example.org/feed\n")
    build(settings, valid)
    dest = settings.derived_dir / "rss_signals.json"
    before = dest.read_bytes()
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("feeds:\n  news: http://example.org/feed\n")
    try:
        build(settings, invalid)
        assert False, "invalid config should fail"
    except ValueError:
        pass
    assert dest.read_bytes() == before
