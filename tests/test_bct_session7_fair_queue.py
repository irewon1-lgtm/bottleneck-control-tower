"""Fair queue opt-in must retain legacy CPU acquisition and global backlog counts."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json
import sqlite3
import pytest
from bct.future_fair_queue import select,VERSION

NOW=datetime(2026,11,13,2,0,tzinfo=timezone.utc)

def item(i,age=800,host=None,title="Orders for gas turbines increased in 2028"):
    return ({
        "id":str(i),"title":title,"snippet":"",
        "url":f"https://{host or ('host'+str(i%10)+'.example')}/{i}",
        "collected_at":(NOW-timedelta(hours=age)).isoformat(),
    },"fingerprint",{})

def screen_metadata(text):
    paths=[]
    if "orders" in text.lower():paths.append("DEMAND")
    if "capacity" in text.lower():paths.append("SUPPLY")
    return {"discovery_paths":paths}

def narrow_metadata(title,snippet):
    return [{"signal":"DEMAND"}] if "orders" in title.lower() else []


def test_fair_120_uses_exact_mixed_recent_and_older_eligible_rows():
    jobs=[item(i,age=2 if i>=80 else 800) for i in range(120)]
    selected,receipt=select(jobs,limit=50,now=NOW,
                            screener=screen_metadata,narrow=narrow_metadata)
    assert receipt["fair_queue_version"]==VERSION
    assert receipt["fair_queue_selected"]==50
    assert receipt["fair_queue_recent"]==20
    assert receipt["fair_queue_older"]==30
    assert receipt["fair_queue_max_host"]<=6
    assert len({r[0]["id"] for r in selected})==50
    assert len(jobs)==120


def test_no_recent_does_not_starve_old_backlog():
    jobs=[item(i) for i in range(24)]
    result,metrics=select(jobs,limit=20,now=NOW,screener=screen_metadata,narrow=narrow_metadata)
    assert metrics["fair_queue_recent"]==0
    assert metrics["fair_queue_older"]==20
    assert len(result)==20


def test_no_old_does_not_starve_recent_new_articles():
    jobs=[item(i,age=2) for i in range(24)]
    result,metrics=select(jobs,limit=20,now=NOW,screener=screen_metadata,narrow=narrow_metadata)
    assert metrics["fair_queue_recent"]==20
    assert len(result)==20


def test_publisher_host_limit_prevents_single_domain_hogging():
    jobs=[item(i,host="all.example") for i in range(30)]
    chosen,metrics=select(jobs,limit=20,now=NOW,screener=screen_metadata,narrow=narrow_metadata)
    assert len(chosen)==6
    assert metrics["fair_queue_max_host"]==6
    assert metrics["fair_queue_input_due"]==30
    assert metrics["fair_queue_discarded_due_to_host_and_budget"]==24


@pytest.mark.parametrize("limit",[-1,0,301])
def test_free_budget_bounds_fail_closed(limit):
    with pytest.raises(ValueError,match="FAIR_QUEUE_BOUNDS"):
        select([item(1)],limit=limit,now=NOW,screener=screen_metadata)


def test_duplicate_source_id_not_double_fetched():
    with pytest.raises(ValueError,match="DUPLICATE_ID"):
        select([item(1),item(1)],limit=3,now=NOW,screener=screen_metadata)


def _db(tmp_path):
    db=tmp_path/"rss.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE radar_items(
           id TEXT PRIMARY KEY,title TEXT,url TEXT,source TEXT,
           collected_at TEXT,updated_at TEXT,status TEXT,published_at TEXT,
           snippet TEXT)""")
        for i in range(8):
            older=i<4
            timestamp=(NOW-timedelta(hours=800 if older else 2)).isoformat()
            conn.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?,?)",(
                str(i),"Firm orders for gas turbines increased in 2028",
                f"https://host{i}.example/story/{i}","rss",
                timestamp,timestamp,"active",timestamp,"Firm physical orders"))
    return db


def test_opt_in_existing_engine_fetches_recent_and_old_without_reset(tmp_path,monkeypatch):
    from bct.future_bottleneck import run
    db=_db(tmp_path)
    called_old=[];called_new=[]
    def old_fetch(url):
        called_old.append(url)
        return ("Firm orders for gas turbines increased.", "SYNTHETIC")
    def new_fetch(url):
        called_new.append(url)
        return ("Firm orders for gas turbines increased.", "SYNTHETIC")
    monkeypatch.delenv("BCT_FAIR_QUEUE_MODE",raising=False)
    baseline=run(db,tmp_path/"old-sidecar.json",limit=4,workers=1,
                 fetcher=old_fetch,cache_dir=tmp_path/"old-cache",detection_mode="SYNTHETIC")
    assert len(called_old)==4
    assert not any("/story/4" in x for x in called_old)
    assert baseline["summary"]["pending_due"]==4
    monkeypatch.setenv("BCT_FAIR_QUEUE_MODE","balanced-v1")
    balanced=run(db,tmp_path/"balanced-sidecar.json",limit=4,workers=1,
                 fetcher=new_fetch,cache_dir=tmp_path/"balanced-cache",
                 detection_mode="SYNTHETIC")
    assert len(called_new)==4
    assert sum(any(f"/story/{i}" in x for x in called_new) for i in range(4,8))==2
    assert sum(any(f"/story/{i}" in x for x in called_new) for i in range(4))==2
    assert balanced["summary"]["pending_due"]==4
    assert balanced["summary"]["active_unprocessed_total"]==4
    assert balanced["summary"]["fair_queue_recent"]==2
    assert balanced["summary"]["fair_queue_older"]==2
    assert balanced["summary"]["source_wide_scan"] is True
    assert set(json.loads((tmp_path/"balanced-sidecar.json").read_text())["results"])==set(
       str(i) for i in range(8) if any(f"/story/{i}" in x for x in called_new))


def test_operating_atomic_queue_does_not_depend_on_all_cpu_reads_succeeding():
    """Failing one native inference keeps FAIL yet does not skip saved queue."""
    import yaml
    root=Path(__file__).resolve().parents[1]
    workflow=yaml.safe_load((root/".github/workflows/future-bottleneck.yml").read_text())
    steps=workflow["jobs"]["candidates"]["steps"]
    ids={step["id"]:step for step in steps if "id" in step}
    assert "verified_operating_restore" in ids
    assert "candidate_sidecar_publish" in ids
    assert "full_body_cpu_reader" in ids
    publisher=ids["atomic_operating_queue"]
    guard=publisher["if"]
    assert "success()" in guard and "failure()" in guard
    assert "steps.full_body_cpu_reader.conclusion == 'failure'" in guard
    assert "steps.candidate_sidecar_publish.conclusion == 'success'" in guard
    assert "steps.verified_operating_restore.conclusion == 'success'" in guard
    assert "continue-on-error" not in ids["full_body_cpu_reader"]
    assert "bct_publish_operating_queue.py" in publisher["run"]


def test_runtime_selection_flag_does_not_leak_into_regression_suite():
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root/'.github/workflows/future-bottleneck.yml').read_text())
    job = workflow['jobs']['candidates']
    assert (job.get('env') or {}).get('BCT_FAIR_QUEUE_MODE') is None
    steps = {v['name']:v for v in job['steps'] if 'name' in v}
    assert (steps['Run full regression suite'].get('env') or {}).get('BCT_FAIR_QUEUE_MODE') is None
    assert steps['Screen article bodies without any AI API']['env']['BCT_FAIR_QUEUE_MODE']=='balanced-v1'
    assert steps['Publish candidate sidecar only']['env']['BCT_FAIR_QUEUE_MODE']=='balanced-v1'
    assert (steps['Read FULL sources with pinned cost-zero CPU reader'].get('env') or {}).get('BCT_FAIR_QUEUE_MODE') is None
