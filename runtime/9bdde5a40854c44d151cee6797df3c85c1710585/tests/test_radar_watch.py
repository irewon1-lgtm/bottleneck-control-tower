from sqlalchemy import func, select

from bct.backup import create_backup, restore_backup
from bct.config import Settings
from bct.db import session_factory
from bct.models import AuditLog, RadarItem
from bct.radar_families import build
from bct.radar_watch import current, record_material_change, record_review


def test_watch_review_is_audited_and_reprints_do_not_repromote(setup, tmp_path):
    settings, sf = setup
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  eia: https://eia.example.org/feed\n"
                     "  logistics: https://logistics.example.org/feed\n"
                     "  new: https://new.example.org/feed\n")
    with sf.begin() as db:
        for id_, host, title, snippet in (
            ("eia", "eia.example.org", "Tight global supplies of distillate fuel oil",
             "Petroleum refinery distillate fuel oil, often sold as diesel."),
            ("logistics", "logistics.example.org", "Shortages of diesel, jet fuel and marine fuels",
             "Petroleum refining network could cause shortages if disrupted."),
            ("reprint", "new.example.org", "Diesel shortage if refining stops",
             "Petroleum refining disruption could cause a diesel shortage."),
        ):
            db.add(RadarItem(id=id_, source=host, external_id=id_, title=title,
                             url=f"https://{host}/{id_}", source_type="NEWS", snippet=snippet))
    details = dict(status="WATCH", confirmed_scope=["diesel", "distillate fuel oil", "gasoil"],
                   unresolved_scope=["jet fuel", "marine fuel", "petrochemical feedstock"],
                   reviewed_article_ids=["eia", "logistics"], lineage_roots=["EIA", "IEA"],
                   review_note="One direct assertion; second article is conditional and cites IEA.")
    with sf.begin() as db:
        assert record_review(db, "refined petroleum products", **details)
        assert not record_review(db, "refined petroleum products", **details)
    first = next(x for x in build(settings, feeds)["families"] if x["family"] == "refined petroleum products")
    assert first["promote"] and first["core_status"] == "WATCH"
    assert not first["new_promote"]
    assert not first["re_review_required"] and first["confirmed_scope"] == details["confirmed_scope"]
    with sf.begin() as db:
        assert not record_material_change(db, "refined petroleum products",
                                          trigger="NEW_INDEPENDENT_CONSTRAINT", article_id="reprint",
                                          lineage_root="IEA", note="Conditional IEA rewrite",
                                          original_measurement=False, current_fact=False)
        assert not record_material_change(db, "refined petroleum products",
                                          trigger="NEW_INDEPENDENT_CONSTRAINT", article_id="reprint",
                                          lineage_root="IEA", note="Same upstream source",
                                          original_measurement=True, current_fact=True)
    second = next(x for x in build(settings, feeds)["families"] if x["family"] == "refined petroleum products")
    assert second == first
    with sf.begin() as db:
        assert record_material_change(db, "refined petroleum products",
                                      trigger="METRIC_WORSENING", article_id="reprint",
                                      lineage_root="IEA", note="Manually verified new measured stock decline",
                                      original_measurement=True, current_fact=True)
        assert not record_material_change(db, "refined petroleum products",
                                          trigger="METRIC_WORSENING", article_id="reprint",
                                          lineage_root="IEA", note="Manually verified new measured stock decline",
                                          original_measurement=True, current_fact=True)
    pending = next(x for x in build(settings, feeds)["families"] if x["family"] == "refined petroleum products")
    assert pending["core_status"] == "WATCH" and pending["re_review_required"]
    assert pending["re_review_triggers"] == ["METRIC_WORSENING"]
    with sf.begin() as db:
        assert record_review(db, "refined petroleum products", **details)
        assert not current(db, "refined petroleum products")["re_review_required"]
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == "radar_family.review")) == 2


def test_new_independent_source_and_scope_need_manual_confirmation(setup):
    _, sf = setup
    with sf.begin() as db:
        db.add_all([RadarItem(id=id_, source="example.org", external_id=id_, title="Diesel shortage",
                              url=f"https://example.org/{id_}", source_type="NEWS")
                    for id_ in ("old", "new")])
    with sf.begin() as db:
        record_review(db, "refined petroleum products", status="WATCH",
                      confirmed_scope=["diesel"], unresolved_scope=["jet fuel"],
                      reviewed_article_ids=["old"], lineage_roots=["EIA"], review_note="Manual review")
        assert not record_material_change(db, "refined petroleum products",
                                          trigger="SCOPE_EXPANSION", article_id="new",
                                          lineage_root="NewAgency", product="jet fuel",
                                          note="Only a hypothetical shortage", original_measurement=True,
                                          current_fact=False)
        assert record_material_change(db, "refined petroleum products",
                                      trigger="SCOPE_EXPANSION", article_id="new",
                                      lineage_root="NewAgency", product="jet fuel",
                                      note="Verified current jet fuel constraint", original_measurement=True,
                                      current_fact=True)
        assert current(db, "refined petroleum products")["re_review_required"]


def test_watch_audit_survives_backup_restore(setup, tmp_path):
    settings, sf = setup
    with sf.begin() as db:
        db.add(RadarItem(id="eia", source="eia.example.org", external_id="one",
                         title="Tight global supplies of distillate fuel oil",
                         snippet="Petroleum refining and diesel.",
                         url="https://eia.example.org/one", source_type="NEWS"))
        db.flush()
        record_review(db, "refined petroleum products", status="WATCH",
                      confirmed_scope=["diesel", "distillate fuel oil"],
                      unresolved_scope=["jet fuel"], reviewed_article_ids=["eia"],
                      lineage_roots=["EIA"], review_note="Current distillate pressure")
    backup = create_backup(settings)
    restored = Settings(restore_backup(backup, tmp_path / "restored"))
    with session_factory(restored)() as db:
        row = current(db, "refined petroleum products")
        assert row["status"] == "WATCH" and row["confirmed_scope"] == ["diesel", "distillate fuel oil"]
