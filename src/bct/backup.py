import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _referenced(db_path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        has_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_documents'").fetchone()
        return conn.execute("SELECT DISTINCT relative_path, sha256 FROM raw_documents").fetchall() if has_table else []


def create_backup(settings: Settings) -> Path:
    if not settings.db_path.is_file():
        raise FileNotFoundError(settings.db_path)
    settings.mkdirs()
    work = Path(tempfile.mkdtemp(prefix=".backup-", dir=settings.backups_dir))
    published = False
    try:
        snapshot = work / "canonical.sqlite3"
        with sqlite3.connect(settings.db_path) as live, sqlite3.connect(snapshot) as target:
            live.backup(target)
        entries = {"canonical.sqlite3": _sha(snapshot)}
        for relative, digest in _referenced(snapshot):
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("sha256",):
                raise ValueError("invalid raw path in database")
            source = settings.root / "raw" / path
            if _sha(source) != digest:
                raise IOError(f"raw integrity failure: {relative}")
            destination = work / "raw" / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if _sha(destination) != digest:
                raise IOError("raw changed during backup")
            entries[f"raw/{relative}"] = digest
        (work / "manifest.json").write_text(json.dumps({"format": 1, "files": entries},
            indent=2, sort_keys=True), encoding="utf-8")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = settings.backups_dir / f"backup-{stamp}"
        work.rename(dest)
        published = True
        return dest
    finally:
        if not published:
            shutil.rmtree(work, ignore_errors=True)


def verify_backup(backup: Path) -> dict:
    backup = Path(backup).resolve()
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("unsupported backup manifest")
    expected = {"canonical.sqlite3"}
    for path, digest in _referenced(backup / "canonical.sqlite3"):
        expected.add(f"raw/{path}")
        if manifest["files"].get(f"raw/{path}") != digest:
            raise ValueError("raw index mismatch")
    if set(manifest["files"]) != expected:
        raise ValueError("unexpected backup inventory")
    for name, digest in manifest["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not digest or _sha(backup / relative) != digest:
            raise IOError(f"backup hash mismatch: {name}")
    with sqlite3.connect(backup / "canonical.sqlite3") as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise IOError("SQLite integrity check failed")
    return manifest


def restore_backup(backup: Path, target_root: Path) -> Path:
    """Restore to an absent destination only, never overwrite live data."""
    verify_backup(backup)
    target = Path(target_root).resolve()
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".restore-", dir=target.parent))
    try:
        manifest = json.loads((Path(backup) / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["files"]:
            dest = temp / ("canonical/canonical.sqlite3" if name == "canonical.sqlite3" else name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(backup) / name, dest)
            if _sha(dest) != manifest["files"][name]:
                raise IOError("copy failed verification")
        for area in ("staging", "derived", "backups"):
            (temp / area).mkdir()
        temp.rename(target)
        return target
    finally:
        if temp.exists():
            shutil.rmtree(temp)
