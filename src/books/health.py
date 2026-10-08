from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .config import load_settings
from .db import Database

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][\w]*)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def expected_tables() -> frozenset[str]:
    """Table names the current schema must contain.

    Derived from the packaged migration sources (plus the ``schema_migrations``
    ledger that :meth:`Database.migrate` maintains itself), so validation
    follows schema changes instead of drifting behind them.
    """
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    tables: set[str] = set()
    for migration in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
        tables.update(
            match.group(1)
            for match in _CREATE_TABLE_RE.finditer(
                migration.read_text(encoding="utf-8")
            )
        )
    tables.add("schema_migrations")
    return frozenset(tables)


def missing_tables(conn: sqlite3.Connection) -> frozenset[str]:
    """Names from :func:`expected_tables` absent from the connected database."""
    present = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    return expected_tables() - present


def validate_database(path: str | Path) -> None:
    """Raise a descriptive :class:`ValueError` unless ``path`` is a full BOOKS DB."""
    conn = sqlite3.connect(path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("SQLite integrity check failed")
        missing = missing_tables(conn)
        if missing:
            raise ValueError(
                "database is not a complete BOOKS database; "
                f"missing tables: {', '.join(sorted(missing))}"
            )
    except sqlite3.DatabaseError as exc:
        raise ValueError("invalid BOOKS database") from exc
    finally:
        conn.close()


def main() -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    with db.connect() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return 1
        if missing_tables(conn):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
