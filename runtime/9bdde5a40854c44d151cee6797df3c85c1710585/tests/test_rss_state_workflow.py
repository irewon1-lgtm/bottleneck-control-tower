import importlib.util
import sqlite3
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/rss_state.py"
SPEC = importlib.util.spec_from_file_location("rss_state", SCRIPT)
rss_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rss_state)


def _db(path, names):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE radar_items (name TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO radar_items VALUES (?)", [(name,) for name in names])


def test_two_runs_resume_and_keep_previous_snapshot(tmp_path):
    first = tmp_path / "first.sqlite3"
    _db(first, ["one", "two"])
    branch = tmp_path / "data"
    assert rss_state.save(first, branch, "1")["radar_items"] == 2
    restored = tmp_path / "second.sqlite3"
    rss_state.load(branch, restored)
    with sqlite3.connect(restored) as db:
        db.execute("INSERT OR IGNORE INTO radar_items VALUES ('one')")
        db.execute("INSERT OR IGNORE INTO radar_items VALUES ('three')")
    state = rss_state.save(restored, branch, "2")
    assert state["radar_items"] == 3
    assert state["previous_radar_items"] == 2
    assert rss_state.count_and_check(branch / "canonical.previous.sqlite3") == 2
    assert rss_state.validate(branch)["radar_items"] == 3


def test_corruption_or_missing_snapshot_cannot_reset_database(tmp_path):
    live = tmp_path / "live.sqlite3"
    _db(live, ["one"])
    branch = tmp_path / "data"
    rss_state.save(live, branch, "1")
    (branch / "canonical.sqlite3").write_bytes(b"broken")
    with pytest.raises(ValueError, match="hash mismatch"):
        rss_state.load(branch, tmp_path / "restored.sqlite3")
    assert not (tmp_path / "restored.sqlite3").exists()
    with pytest.raises(ValueError, match="hash mismatch"):
        rss_state.save(live, branch, "2")
