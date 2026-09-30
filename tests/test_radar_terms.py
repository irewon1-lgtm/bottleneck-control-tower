import json

from bct.models import RadarItem
from bct.radar_signals import extract
from bct.radar_terms import build, terms


def review(title, snippet=None):
    return terms(title, snippet, extract(title, snippet))


def test_product_phrases_noise_and_unresolved():
    for title, expected in (
        ("Solid rocket motor shortage", "solid rocket motor"),
        ("Large power transformer lead times rise", "large power transformer"),
        ("HBM memory capacity constrained", "hbm memory"),
        ("Gas turbine production delay", "gas turbine"),
        ("Pentagon to double AMRAAM production", "AMRAAM"),
        ("Uranium shortage", "uranium"),
    ):
        assert expected in review(title)["candidate_terms"]
    assert review("No related signal")["candidate_terms"] == []
    ambiguous = review("Data movement to address memory bottlenecks")
    assert ambiguous["candidate_terms"] == []
    assert ambiguous["unresolved_terms"][0]["status"] == "UNRESOLVED_TERM"
    noisy = review("News", "Shortages of skilled workers and contractors")
    assert noisy["candidate_terms"] == []
    assert noisy["removed_noise_terms"] == ["skilled"]
    assert noisy["unresolved_terms"][0]["status"] == "UNRESOLVED_TERM"
    assert review("Uranium project updates", "Diesel shortages")["candidate_terms"] == ["diesel"]


def test_explicit_lists_and_product_model():
    assert review("Refining", "Shortages of diesel, jet fuel, marine fuels and petrochemical feedstocks if transport fails")['candidate_terms'] == [
        'diesel', 'jet fuel', 'marine fuel', 'petrochemical feedstock']
    model = review("Sony PS5 Pro orders", "Device shortages led to PlayStation 5 Pro lottery")
    assert model['candidate_terms'] == ['PlayStation 5 Pro']
    assert model['removed_noise_terms'] == ['device']


def test_derived_review_is_idempotent_and_does_not_mutate_radar(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        db.add(RadarItem(id="rss-1", source="example.org", external_id="one",
                         title="Gas turbine production delay", url="https://example.org/one",
                         source_type="NEWS"))
        db.add(RadarItem(id="rss-2", source="example.org", external_id="two",
                         title="A plain story", url="https://example.org/two", source_type="NEWS"))
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  one: https://example.org/feed\n")
    first = build(settings, feeds)
    assert (first['processed_articles'], first['signal_articles']) == (2, 1)
    assert first['reviews'][0]['candidate_terms'] == ['gas turbine']
    path = settings.derived_dir / 'rss_term_review.json'
    before = path.read_bytes()
    assert build(settings, feeds) == first
    assert path.read_bytes() == before
    with sf() as db:
        assert db.get(RadarItem, 'rss-1').title == 'Gas turbine production delay'
    assert json.loads(before)['reviews'][0]['radar_item_id'] == 'rss-1'
