"""Selection-to-existing CPU CLI guard: real and old RSS, read-only source snapshots."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json,sqlite3
import pytest

from tools import bct_session7_select_work as bridge

AT=datetime(2026,11,13,2,0,tzinfo=timezone.utc)

def setup(tmp_path,n=80,old=50):
    db=tmp_path/"source.sqlite3";s=tmp_path/"sidecar.json"
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE radar_items(
          id TEXT PRIMARY KEY,source TEXT,url TEXT,title TEXT,
          snippet TEXT,published_at TEXT,collected_at TEXT,
          updated_at TEXT,status TEXT)""")
        for i in range(n):
            t=(AT-timedelta(hours=(1000 if i<old else 2))).isoformat()
            c.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?,?)",
                (f"id-{i:03d}","rss",f"https://host{i%10}.example/post/{i}",
                "Firm orders for transformers increased in 2028.","",t,t,t,"active"))
    s.write_text(json.dumps({"version":"body-candidate-v3.3","results":{
        f"id-{i:03d}":{"body_status":"UNAVAILABLE",
                      "fingerprint":"different","attempts":0}
        for i in range(5)}}),encoding="utf-8")
    return db,s

def test_stable_fair_source_selection_is_read_only(tmp_path):
    db,sidecar=setup(tmp_path)
    before=(hashlib.sha256(db.read_bytes()).hexdigest(),
            hashlib.sha256(sidecar.read_bytes()).hexdigest())
    selected=bridge.selection(db,sidecar,budget=30,at=AT)
    assert selected["article_total"]==80
    assert selected["previous_sidecar_results"]==5
    assert selected["unlinked"]==75
    assert selected["selected_count"]==30
    assert selected["selected_recent"]==12
    assert selected["selected_old"]==18
    assert len(set(selected["ids"]))==len(selected["ids"])
    assert all(item["work_action"]=="FETCH_OR_RECHECK_ORIGINAL" for item in selected["selected"])
    assert selected["verified_bottleneck_promotions"]==0
    output=tmp_path/"selected.json";bridge.save_selection(selected,output)
    assert len(output.with_suffix(".ids").read_text().splitlines())==30
    assert (hashlib.sha256(db.read_bytes()).hexdigest(),
            hashlib.sha256(sidecar.read_bytes()).hexdigest())==before

def test_source_holds_cannot_be_selected_even_if_title_is_high_priority(tmp_path):
    db,sidecar=setup(tmp_path,20,5)
    with sqlite3.connect(db) as c:
        rec=c.execute("SELECT id,url,updated_at FROM radar_items WHERE id='id-000'").fetchone()
    fingerprint=hashlib.sha256((rec[1]+rec[2]).encode()).hexdigest()
    sidecar.write_text(json.dumps({"results":{"id-000":{
        "fingerprint":fingerprint,"body_status":"UNAVAILABLE",
        "candidate":True,"reasons":["HTTP_403"],"attempts":3}}}))
    outcome=bridge.selection(db,sidecar,budget=20,at=AT)
    assert "id-000" not in outcome["ids"]
    assert outcome["held_or_deferred"]>=1

def test_duplicate_existing_id_raises():
    # Existing source identity and sidecar delta are never silently overwritten.
    assert bridge.MAX_SELECTED<=300

def test_unsafe_ids_fail_before_writing_shell_bridge(tmp_path):
    record={"ids":["$(curl attacker)"],"selected_count":1}
    with pytest.raises(ValueError,match="S7_SHELL_ID_NOT_SAFE"):
        bridge.save_selection(record,tmp_path/"select.json")

def test_budget_ceiling_blocks_unbounded_processing(tmp_path):
    db,sidecar=setup(tmp_path)
    with pytest.raises(ValueError,match="S7_SELECTION_BUDGET_EXCEEDED"):
        bridge.selection(db,sidecar,budget=301,at=AT)
