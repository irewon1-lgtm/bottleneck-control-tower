"""Validate and transfer the RSS workflow's public SQLite snapshot."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def count_and_check(path: Path) -> int:
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        return db.execute("SELECT count(*) FROM radar_items").fetchone()[0]


def validate(directory: Path) -> dict:
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    for key, filename in (("sha256", "canonical.sqlite3"),
                          ("previous_sha256", "canonical.previous.sqlite3")):
        path = directory / filename
        if not path.is_file() or digest(path) != state[key]:
            raise ValueError(f"snapshot hash mismatch: {filename}")
        count_and_check(path)
    if count_and_check(directory / "canonical.sqlite3") != state["radar_items"]:
        raise ValueError("snapshot row count mismatch")
    return state


def load(directory: Path, target: Path) -> None:
    validate(directory)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(target)
    shutil.copy2(directory / "canonical.sqlite3", target)
    if digest(target) != digest(directory / "canonical.sqlite3"):
        raise IOError("restore copy hash mismatch")


def save(live: Path, directory: Path, run_id: str) -> dict:
    previous = validate(directory) if (directory / "state.json").exists() else None
    directory.mkdir(parents=True, exist_ok=True)
    if previous:
        # Preserve the last valid snapshot before replacing it.
        shutil.copy2(directory / "canonical.sqlite3",
                     directory / "canonical.previous.sqlite3")
    snapshot = directory / "canonical.next.sqlite3"
    try:
        with sqlite3.connect(live) as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        total = count_and_check(snapshot)
        if previous and total < previous["radar_items"]:
            raise ValueError("radar article count decreased")
        if not previous:
            shutil.copy2(snapshot, directory / "canonical.previous.sqlite3")
        snapshot.replace(directory / "canonical.sqlite3")
        state = {"sha256": digest(directory / "canonical.sqlite3"),
                 "previous_sha256": digest(directory / "canonical.previous.sqlite3"),
                 "radar_items": total, "previous_radar_items":
                     previous["radar_items"] if previous else 0,
                 "run_id": run_id}
        (directory / "state.json").write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate(directory)
        return state
    finally:
        snapshot.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("load", "save"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.operation == "load":
        load(args.source, args.destination)
    else:
        if not args.run_id:
            parser.error("--run-id required for save")
        result = save(args.source, args.destination, args.run_id)
        print(json.dumps({k: v for k, v in result.items() if "sha256" not in k}))
