from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Any

from .models import Book
from .normalization import normalize_isbn, normalize_text


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

    def create_book(self, book: Book, book_id: str | None = None) -> str:
        identifier = book_id or str(uuid.uuid4())
        payload = {
            "id": identifier,
            "title": book.title,
            "original_title": book.original_title,
            "authors_json": json.dumps(book.authors, ensure_ascii=False),
            "translators_json": json.dumps(book.translators, ensure_ascii=False),
            "publisher": book.publisher,
            "pages": book.pages,
            "publication_year": book.publication_year,
            "isbn10": book.isbn10,
            "isbn13": book.isbn13,
            "language": book.language,
            "genres_json": json.dumps(book.genres, ensure_ascii=False),
            "subjects_json": json.dumps(book.subjects, ensure_ascii=False),
            "summary": book.summary,
            "cover_url": book.cover_url,
            "source_ids_json": json.dumps(dict(book.source_ids), ensure_ascii=False),
            "notes": book.notes,
        }
        return self.create(payload)

    def get_by_isbn(self, isbn: str) -> sqlite3.Row | None:
        normalized = str(isbn).strip()
        if not normalized:
            return None
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM books WHERE isbn10 = ? OR isbn13 = ? LIMIT 1",
                (normalized, normalized),
            ).fetchone()

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

    def search(self, query: str, limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
        normalized = normalize_text(query)
        if not normalized:
            raise ValueError("query must not be empty")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        pattern = f"%{normalized}%"
        spaced_pattern = f"%{normalized.replace(chr(8204), " ")}%"
        isbn_normalized = normalize_isbn(normalized) or normalized
        isbn_pattern = f"%{isbn_normalized}%"
        columns = (
            "title", "original_title", "authors_json", "translators_json",
            "publisher", "isbn10", "isbn13",
        )
        clauses = []
        params: list[str] = []
        for column in columns:
            expression = f"REPLACE({column}, char(8204), ' ')"
            clauses.append(f"{expression} LIKE ?")
            params.append(spaced_pattern)
            clauses.append(f"{column} LIKE ?")
            params.append(isbn_pattern if column in {"isbn10", "isbn13"} else pattern)

        clauses_sql = " OR ".join(clauses)
        with self.db.connect() as conn:
            return conn.execute(
                f"SELECT * FROM books WHERE {clauses_sql} "
                "ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()

    def delete(self, book_id: str) -> bool:
        with transaction(self.db) as conn:
            result = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            return result.rowcount == 1
