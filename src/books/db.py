from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Any


class Database:
    """Small SQLite boundary with migrations and explicit transactions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def migrate(self) -> int:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self.connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            applied = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            count = 0
            for migration in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration.name[:3])
                if version in applied:
                    continue
                conn.executescript(migration.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    (version, migration.name),
                )
                count += 1
        return count


@contextmanager
def transaction(db: Database) -> Iterator[sqlite3.Connection]:
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class BookRepository:
    """Persistence operations for the initial Book storage contract."""

    _JSON_DEFAULTS = {
        "authors_json": "[]",
        "translators_json": "[]",
        "genres_json": "[]",
        "subjects_json": "[]",
        "source_ids_json": "{}",
    }

    def __init__(self, db: Database):
        self.db = db

    def create(self, book: Mapping[str, Any]) -> str:
        book_id = str(book["id"])
        now = datetime.now(timezone.utc).isoformat()
        columns = (
            "id", "title", "original_title", "authors_json", "translators_json",
            "publisher", "pages", "publication_year", "isbn10", "isbn13", "language",
            "genres_json", "subjects_json", "summary", "cover_url", "source_ids_json",
            "notes", "created_at", "updated_at",
        )
        values = []
        for column in columns:
            if column in ("created_at", "updated_at"):
                value = book.get(column, now)
            else:
                value = book.get(column, self._JSON_DEFAULTS.get(column))

            values.append(value)

        if not book.get("title"):
            raise ValueError("title is required")

        with transaction(self.db) as conn:
            conn.execute(
                f"INSERT INTO books ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(values),
            )
        return book_id

    def get(self, book_id: str) -> sqlite3.Row | None:
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    def list(self, limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM books ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

    def delete(self, book_id: str) -> bool:
        with transaction(self.db) as conn:
            result = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            return result.rowcount == 1
