from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import sqlite3
from .config import Settings


def engine_for(settings: Settings):
    engine = create_engine(f"sqlite:///{settings.db_path}", future=True,
                           connect_args={"timeout": settings.busy_timeout_ms / 1000})

    @event.listens_for(engine, "connect")
    def setup_sqlite(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute(f"PRAGMA busy_timeout={settings.busy_timeout_ms}")
        cur.close()

    return engine


def session_factory(settings: Settings):
    return sessionmaker(bind=engine_for(settings), expire_on_commit=False)


def alembic_config(settings: Settings) -> Config:
    base = Path(__file__).resolve().parents[2]
    config = Config(str(base / "alembic.ini"))
    config.set_main_option("script_location", str(base / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")
    return config


def migrate(settings: Settings, *, backup_existing=True) -> Path | None:
    settings.mkdirs()
    backup = None
    current = None
    if settings.db_path.exists() and settings.db_path.stat().st_size:
        with sqlite3.connect(settings.db_path) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone():
                row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                current = row[0] if row else None
    if current == ScriptDirectory.from_config(alembic_config(settings)).get_current_head():
        return None
    if backup_existing and settings.db_path.exists() and settings.db_path.stat().st_size:
        from .backup import create_backup
        backup = create_backup(settings)
    command.upgrade(alembic_config(settings), "head")
    return backup
