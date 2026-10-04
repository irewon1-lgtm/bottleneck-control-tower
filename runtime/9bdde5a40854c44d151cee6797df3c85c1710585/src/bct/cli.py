import argparse
import json
import logging
import sys
from pathlib import Path

from .backup import create_backup, restore_backup, verify_backup
from .config import load_settings
from .db import migrate
from .health import health, rebuild_derived


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "event": record.getMessage(),
                           "logger": record.name}, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "migrate", "health", "backup", "rebuild-derived"):
        commands.add_parser(name)
    commands.choices["health"].add_argument("--deep", action="store_true")
    restore = commands.add_parser("restore")
    restore.add_argument("backup_path", type=Path)
    restore.add_argument("--to", type=Path, required=True)
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)
    if args.command in ("init", "migrate"):
        backup = migrate(settings)
        result = {"migration": "head", "pre_migration_backup": str(backup) if backup else None}
    elif args.command == "health":
        result = health(settings, deep=args.deep)
    elif args.command == "backup":
        result = {"backup": str(create_backup(settings))}
    elif args.command == "restore":
        result = {"restored_to": str(restore_backup(args.backup_path, args.to))}
    else:
        result = {"derived_records": rebuild_derived(settings)}
    logging.info("command.completed %s", args.command)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
