from bct.models import RadarItem
from bct.radar_pressure_relief import build
from bct.radar_signals import extract
from bct.radar_terms import terms


def test_narrow_new_phrases_keep_original_signal_names():
    cases = [
        ("Tight global supplies of distillate fuel oil", "SHORTAGE", "distillate fuel oil"),
        ("Plans for a new steel mill", "CAPACITY_EXPANSION", "steel"),
        ("Opening of a new 300mm fab", "CAPACITY_EXPANSION", "300mm semiconductor wafer"),
        ("White House Announces Plans for $15 Billion Steel Mill in Iowa", "CAPACITY_EXPANSION", "steel"),
        ("VSMC Celebrates the Grand Opening of Its First 300mm Fab in Singapore", "CAPACITY_EXPANSION", "300mm semiconductor wafer"),
        ("Radar-satellite maker to double radar-satellite capacity", "CAPACITY_EXPANSION", "radar satellite"),
    ]
    for title, signal, term in cases:
        hits = extract(title, None)
        assert signal in {hit["signal"] for hit in hits}
        assert term in terms(title, None, hits)["candidate_terms"]
    assert extract("New supplier selected", None)[0]["signal"] == "CAPACITY_EXPANSION"
    assert extract("Steel prices rise", None) == []


def test_pressure_relief_counts_and_idempotent_rebuild(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        for id_, source, title, date in (
            ("one", "a.example.org", "Steel shortage", "2026-09-01T00:00:00+00:00"),
            ("two", "b.example.org", "New steel mill to ease shortage", "2026-09-03T00:00:00+00:00"),
            ("three", "a.example.org", "New steel mill proposed", "2026-09-02T00:00:00+00:00"),
            ("four", "a.example.org", "AMRAAM production delay", "2026-09-04T00:00:00+00:00"),
            ("five", "a.example.org", "An ordinary article", "2026-09-05T00:00:00+00:00"),
        ):
            db.add(RadarItem(id=id_, source=source, external_id=id_, title=title,
                             url=f"https://{source}/{id_}", source_type="NEWS", published_at=date))
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  a: https://a.example.org/rss\n  b: https://b.example.org/rss\n")
    first = build(settings, feeds)
    assert first["processed_articles"] == 5
    assert first["new_article_signals"] == 5
    candidates = {row["candidate_term"]: row for row in first["candidates"]}
    assert candidates["steel"]["group"] == "BOTH"
    assert (candidates["steel"]["pressure_articles"], candidates["steel"]["relief_articles"]) == (2, 2)
    assert candidates["steel"]["source_count"] == 2
    assert candidates["steel"]["signal_type_count"] == 2
    assert candidates["steel"]["latest_at"] == "2026-09-03T00:00:00+00:00"
    snapshot = (settings.derived_dir / "rss_pressure_relief.json").read_bytes()
    again = build(settings, feeds)
    assert again["new_article_signals"] == 0
    assert again["candidates"] == first["candidates"]
    assert (settings.derived_dir / "rss_pressure_relief.json").read_bytes() != snapshot  # delta updated
    assert build(settings, feeds) == again
    with sf() as db:
        assert db.get(RadarItem, "two").title == "New steel mill to ease shortage"
