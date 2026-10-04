from pathlib import Path

from sqlalchemy import func, select

from bct.models import CollectorRun, RadarItem
from bct.radar_families import build
from bct.rss_cycle import run


def xml(title, url, snippet):
    return (f'<rss version="2.0"><channel><item><title>{title}</title><link>{url}</link>'
            f'<pubDate>Tue, 29 Sep 2026 12:00:00 GMT</pubDate>'
            f'<description>{snippet}</description></item></channel></rss>').encode()


class Transport:
    def __init__(self):
        self.fail = False
        self.first = xml("Tight global supplies of distillate fuel oil",
                         "https://eia.example.org/item-1",
                         "Refining margins: distillate fuel oil, often sold as diesel, is tight.")

    def get(self, url):
        if url.endswith("second"):
            if self.fail:
                raise TimeoutError("sample failure")
            return xml("Refining network faces shortages of diesel, jet fuel, marine fuels and petrochemical feedstocks",
                       "https://logistics.example.org/item-2",
                       "The petroleum refining network has shortages of diesel, jet fuel, marine fuels and petrochemical feedstocks.")
        return self.first


def test_serial_accumulation_failure_isolation_and_contextual_family(setup, tmp_path):
    settings, sf = setup
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  EIA: https://eia.example.org/first\n"
                     "  Logistics: https://logistics.example.org/second\n")
    transport = Transport()
    first = run(settings, feeds, "first", transport=transport)
    family = next(row for row in first["families"] if row["family"] == "refined petroleum products")
    assert (first["saved"], first["duplicates"], first["articles"]) == (2, 0, 2)
    assert (family["pressure_articles"], family["relief_articles"], family["article_count"],
            family["source_count"], family["signal_type_count"], family["promote"]) == (2, 0, 2, 2, 1, True)
    assert family["members"] == ["diesel", "distillate fuel oil", "jet fuel", "marine fuel",
                                  "petrochemical feedstock"]
    second = run(settings, feeds, "second", transport=transport)
    assert (second["saved"], second["duplicates"], second["articles"]) == (0, 2, 2)
    transport.fail = True
    third = run(settings, feeds, "third", transport=transport)
    assert third["failed_feeds"] == ["Logistics"]
    assert third["duplicates"] == 1 and third["articles"] == 2
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(RadarItem)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorRun).where(CollectorRun.status == "failed")) == 1
    transport.fail = False
    fourth = run(settings, feeds, "third", transport=transport)
    assert fourth["failed_feeds"] == [] and fourth["duplicates"] == 1 and fourth["articles"] == 2
    added = xml("Shortage of marine fuel", "https://eia.example.org/item-3",
                "Petroleum refining network and marine fuel supply.")
    new_item = added.split(b"<item>", 1)[1].split(b"</item>", 1)[0]
    transport.first = transport.first.replace(b"</channel>", b"<item>" + new_item + b"</item></channel>")
    fifth = run(settings, feeds, "fifth", transport=transport)
    assert (fifth["saved"], fifth["duplicates"], fifth["articles"]) == (1, 2, 3)
    new_family = next(row for row in fifth["families"] if row["family"] == "refined petroleum products")
    assert (new_family["pressure_articles"], new_family["source_count"]) == (3, 2)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(RadarItem)) == 3


def test_relief_only_and_unrelated_diesel_do_not_promote(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        for id_, host, title, snippet in (
            ("one", "one.example.org", "New steel mill", "Steel capacity expansion planned"),
            ("two", "two.example.org", "Diesel shortage", "Truck stop diesel shortages"),
            ("three", "one.example.org", "New steel mill", "A separate steel mill opened"),
        ):
            db.add(RadarItem(id=id_, source=host, external_id=id_, title=title,
                             url=f"https://{host}/{id_}", snippet=snippet, source_type="NEWS"))
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  one: https://one.example.org/feed\n  two: https://two.example.org/feed\n")
    rows = {row["family"]: row for row in build(settings, feeds)["families"]}
    assert rows["steel"]["relief_articles"] == 2 and not rows["steel"]["promote"]
    assert rows["diesel"]["pressure_articles"] == 1 and not rows["diesel"]["promote"]
    assert "refined petroleum products" not in rows
