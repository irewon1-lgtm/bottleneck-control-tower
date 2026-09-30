from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class Settings:
    root: Path
    database_name: str = "canonical.sqlite3"
    log_level: str = "INFO"
    busy_timeout_ms: int = 5000
    job_lease_seconds: int = 300

    @property
    def db_path(self) -> Path:
        return self.root / "canonical" / self.database_name

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw" / "sha256"

    @property
    def staging_dir(self) -> Path:
        return self.root / "staging"

    @property
    def derived_dir(self) -> Path:
        return self.root / "derived"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    def mkdirs(self) -> None:
        for path in (self.db_path.parent, self.raw_dir, self.staging_dir,
                     self.derived_dir, self.backups_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings(config_path: Path) -> Settings:
    path = Path(config_path).resolve()
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("configuration must be a mapping")
    allowed = {"storage_root", "database_name", "log_level", "sqlite_busy_timeout_ms", "job_lease_seconds"}
    if set(config) - allowed:
        raise ValueError(f"unknown configuration keys: {sorted(set(config) - allowed)}")
    root = Path(config.get("storage_root", "./var"))
    root = (path.parent / root).resolve() if not root.is_absolute() else root.resolve()
    name = config.get("database_name", "canonical.sqlite3")
    if not isinstance(name, str) or Path(name).name != name or name in (".", "..") or not name.endswith(".sqlite3"):
        raise ValueError("database_name must be a plain .sqlite3 filename")
    level = config.get("log_level", "INFO")
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ValueError("invalid log_level")
    timeout = config.get("sqlite_busy_timeout_ms", 5000)
    lease = config.get("job_lease_seconds", 300)
    if type(timeout) is not int or not 0 <= timeout <= 60000:
        raise ValueError("invalid sqlite_busy_timeout_ms")
    if type(lease) is not int or not 1 <= lease <= 86400:
        raise ValueError("invalid job_lease_seconds")
    return Settings(root, name, level, timeout, lease)
