from __future__ import annotations

from .config import load_settings
from .db import Database


def main() -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    with db.connect() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return 1
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "books" not in tables or "schema_migrations" not in tables:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
