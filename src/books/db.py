from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

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
        packaged = Path(__file__).resolve().parent / "migrations"
        working_tree = Path.cwd() / "migrations"
        migrations_dir = packaged if packaged.exists() else working_tree
        if not migrations_dir.exists():
            raise FileNotFoundError(f"migrations directory not found: {migrations_dir}")
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
            migrations_by_version: dict[int, list[Path]] = {}
            for migration in migrations_dir.glob("[0-9][0-9][0-9]_*.sql"):
                migrations_by_version.setdefault(int(migration.name[:3]), []).append(migration)

            count = 0
            for version in sorted(migrations_by_version):
                if version in applied:
                    continue
                migrations = sorted(migrations_by_version[version])
                for migration in migrations:
                    conn.executescript(migration.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    (version, ", ".join(m.name for m in migrations)),
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

    _JSON_DEFAULTS: ClassVar[dict[str, str]] = {
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

    def update_book(self, book_id: str, book: Book) -> bool:
        updated_at = datetime.now(timezone.utc).isoformat()
        values = (
            book.title,
            book.original_title,
            json.dumps(book.authors, ensure_ascii=False),
            json.dumps(book.translators, ensure_ascii=False),
            book.publisher,
            book.pages,
            book.publication_year,
            book.isbn10,
            book.isbn13,
            book.language,
            json.dumps(book.genres, ensure_ascii=False),
            json.dumps(book.subjects, ensure_ascii=False),
            book.summary,
            book.cover_url,
            json.dumps(dict(book.source_ids), ensure_ascii=False),
            book.notes,
            updated_at,
            book_id,
        )
        with transaction(self.db) as conn:
            result = conn.execute(
                """UPDATE books SET
                    title = ?, original_title = ?, authors_json = ?, translators_json = ?,
                    publisher = ?, pages = ?, publication_year = ?, isbn10 = ?, isbn13 = ?,
                    language = ?, genres_json = ?, subjects_json = ?, summary = ?,
                    cover_url = ?, source_ids_json = ?, notes = ?, updated_at = ?
                WHERE id = ?""",
                values,
            )
            return result.rowcount == 1

    def get_by_isbn(self, isbn: str) -> sqlite3.Row | None:
        raw = str(isbn).strip()
        if not raw:
            return None
        normalized = normalize_isbn(raw) or raw
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM books WHERE isbn10 IN (?, ?) OR isbn13 IN (?, ?) LIMIT 1",
                (normalized, raw, normalized, raw),
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
        spaced_query = normalized.replace(chr(8204), " ")
        spaced_pattern = f"%{spaced_query}%"
        isbn_normalized = normalize_isbn(normalized) or normalized
        isbn_pattern = f"%{isbn_normalized}%"
        columns = (
            "title", "original_title", "authors_json", "translators_json",
            "publisher", "isbn10", "isbn13", "genres_json", "subjects_json",
            "summary", "notes",
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

    def filter_books(
        self,
        *,
        genre: str | None = None,
        author: str | None = None,
        publisher: str | None = None,
        publication_year: int | None = None,
        language: str | None = None,
        sort_by: str = "updated_at",
        descending: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        sort_columns = {
            "updated_at": "updated_at",
            "title": "title",
            "publication_year": "publication_year",
            "publisher": "publisher",
        }
        if sort_by not in sort_columns:
            raise ValueError("unsupported sort field")

        clauses: list[str] = []
        params: list[Any] = []

        for column, value in (
            ("genres_json", genre),
            ("authors_json", author),
            ("publisher", publisher),
            ("language", language),
        ):
            if value:
                normalized = normalize_text(value)
                if normalized:
                    clauses.append(f"{column} LIKE ?")
                    params.append(f"%{normalized}%")

        if publication_year is not None:
            clauses.append("publication_year = ?")
            params.append(publication_year)

        where = "WHERE " + " AND ".join(clauses) + " " if clauses else ""
        direction = "DESC" if descending else "ASC"
        order = sort_columns[sort_by]

        with self.db.connect() as conn:
            return conn.execute(
                f"SELECT * FROM books {where}ORDER BY {order} {direction}, id "
                "LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()

    READING_STATUSES: ClassVar[dict[str, str]] = {
        "unread": "نخوانده",
        "reading": "در حال مطالعه",
        "finished": "تمام‌شده",
        "abandoned": "رهاشده",
    }

    def update_reading_status(self, book_id: str, status: str) -> bool:
        if status not in self.READING_STATUSES:
            raise ValueError("unsupported reading status")
        with transaction(self.db) as conn:
            result = conn.execute(
                "UPDATE books SET reading_status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now(timezone.utc).isoformat(), book_id),
            )
            return result.rowcount == 1

    def start_reading(self, book_id: str) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        with transaction(self.db) as conn:
            result = conn.execute(
                "UPDATE books SET reading_started_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, book_id),
            )
            if result.rowcount != 1:
                raise ValueError("book not found")
        return timestamp

    def finish_reading(self, book_id: str) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        with transaction(self.db) as conn:
            row = conn.execute(
                "SELECT reading_started_at FROM books WHERE id = ?",
                (book_id,),
            ).fetchone()
            if row is None:
                raise ValueError("book not found")
            if not row["reading_started_at"]:
                raise ValueError("reading must be started first")
            result = conn.execute(
                "UPDATE books SET reading_finished_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, book_id),
            )
            if result.rowcount != 1:
                raise ValueError("book not found")
        return timestamp

    def update_reading_progress(self, book_id: str, current_page: int) -> int:
        if current_page < 0:
            raise ValueError("current page must be non-negative")

        with transaction(self.db) as conn:
            row = conn.execute(
                "SELECT pages FROM books WHERE id = ?",
                (book_id,),
            ).fetchone()
            if row is None:
                raise ValueError("book not found")
            total_pages = row["pages"]
            if total_pages is None or total_pages <= 0:
                raise ValueError("total pages are required for progress")
            if current_page > total_pages:
                raise ValueError("current page cannot exceed total pages")

            progress = round((current_page / total_pages) * 100)
            conn.execute(
                """UPDATE books
                   SET reading_current_page = ?, reading_progress = ?, updated_at = ?
                   WHERE id = ?""",
                (current_page, progress, datetime.now(timezone.utc).isoformat(), book_id),
            )
            return progress

    def get_personal_data(self, book_id: str) -> sqlite3.Row | None:
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM book_personal WHERE book_id = ?",
                (book_id,),
            ).fetchone()

    def update_personal_data(
        self,
        book_id: str,
        *,
        rating: int | None,
        note: str,
        quote: str,
    ) -> None:
        if rating is not None and not 1 <= rating <= 5:
            raise ValueError("rating must be between 1 and 5")
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
                raise ValueError("book not found")
            timestamp = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO book_personal(book_id, rating, note, quote, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(book_id) DO UPDATE SET
                       rating = excluded.rating,
                       note = excluded.note,
                       quote = excluded.quote,
                       updated_at = excluded.updated_at""",
                (book_id, rating, note.strip(), quote.strip(), timestamp),
            )

    def update_favorite(self, book_id: str, favorite: bool) -> None:
        with transaction(self.db) as conn:
            timestamp = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO book_personal(book_id, favorite, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(book_id) DO UPDATE SET
                       favorite = excluded.favorite,
                       updated_at = excluded.updated_at""",
                (book_id, int(favorite), timestamp),
            )

    def get_organization(self, book_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        with self.db.connect() as conn:
            tags = conn.execute(
                """SELECT t.name FROM tags t
                   JOIN book_tags bt ON bt.tag_id = t.id
                   WHERE bt.book_id = ? ORDER BY t.name""",
                (book_id,),
            ).fetchall()
            shelves = conn.execute(
                """SELECT s.name FROM shelves s
                   JOIN book_shelves bs ON bs.shelf_id = s.id
                   WHERE bs.book_id = ? ORDER BY s.name""",
                (book_id,),
            ).fetchall()
        return (
            tuple(row["name"] for row in tags),
            tuple(row["name"] for row in shelves),
        )

    def set_organization(
        self,
        book_id: str,
        *,
        tags: tuple[str, ...],
        shelves: tuple[str, ...],
    ) -> None:
        clean_tags = tuple(dict.fromkeys(normalize_text(value) for value in tags if normalize_text(value)))
        clean_shelves = tuple(dict.fromkeys(normalize_text(value) for value in shelves if normalize_text(value)))
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
                raise ValueError("book not found")

            conn.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
            conn.execute("DELETE FROM book_shelves WHERE book_id = ?", (book_id,))

            for name in clean_tags:
                tag_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT OR IGNORE INTO tags(id, name) VALUES (?, ?)",
                    (tag_id, name),
                )
                row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
                conn.execute(
                    "INSERT INTO book_tags(book_id, tag_id) VALUES (?, ?)",
                    (book_id, row["id"]),
                )

            for name in clean_shelves:
                shelf_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT OR IGNORE INTO shelves(id, name) VALUES (?, ?)",
                    (shelf_id, name),
                )
                row = conn.execute("SELECT id FROM shelves WHERE name = ?", (name,)).fetchone()
                conn.execute(
                    "INSERT INTO book_shelves(book_id, shelf_id) VALUES (?, ?)",
                    (book_id, row["id"]),
                )

    def get_metadata_cache(
        self,
        provider: str,
        cache_key: str,
        language: str,
        max_age_seconds: int,
    ) -> str | None:
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_seconds
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT payload_json, fetched_at FROM metadata_cache
                   WHERE provider = ? AND cache_key = ? AND language = ?""",
                (provider, cache_key, language),
            ).fetchone()
        if row is None:
            return None
        try:
            fetched = datetime.fromisoformat(row["fetched_at"]).timestamp()
        except ValueError:
            return None
        return row["payload_json"] if fetched >= cutoff else None

    def set_metadata_cache(
        self,
        provider: str,
        cache_key: str,
        language: str,
        payload_json: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with transaction(self.db) as conn:
            conn.execute(
                """INSERT INTO metadata_cache(provider, cache_key, language, payload_json, fetched_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(provider, cache_key, language) DO UPDATE SET
                       payload_json = excluded.payload_json,
                       fetched_at = excluded.fetched_at""",
                (provider, cache_key, language, payload_json, timestamp),
            )

    def reading_statistics(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS count FROM books").fetchone()["count"]
            pages = conn.execute(
                "SELECT COALESCE(SUM(pages), 0) AS total, "
                "COALESCE(SUM(reading_current_page), 0) AS current FROM books"
            ).fetchone()
            status_rows = conn.execute(
                "SELECT reading_status, COUNT(*) AS count "
                "FROM books GROUP BY reading_status ORDER BY reading_status"
            ).fetchall()
            author_rows = conn.execute(
                "SELECT authors_json FROM books"
            ).fetchall()
            progress_rows = conn.execute(
                """SELECT substr(updated_at, 1, 7) AS month,
                          ROUND(AVG(reading_progress), 1) AS progress
                   FROM books
                   GROUP BY month
                   ORDER BY month"""
            ).fetchall()

        authors: set[str] = set()
        for row in author_rows:
            authors.update(
                normalize_text(author).casefold()
                for author in json.loads(row["authors_json"] or "[]")
                if normalize_text(author)
            )

        return {
            "book_count": total,
            "total_pages": pages["total"],
            "current_pages": pages["current"],
            "authors_count": len(authors),
            "status_counts": {
                row["reading_status"]: row["count"] for row in status_rows
            },
            "progress_trend": {
                row["month"]: row["progress"] for row in progress_rows
            },
        }

    def find_duplicates(self, book: Book, exclude_id: str | None = None) -> list[sqlite3.Row]:
        candidates: list[sqlite3.Row] = []
        with self.db.connect() as conn:
            if book.isbn10 or book.isbn13:
                clauses = []
                params: list[str] = []
                if book.isbn10:
                    clauses.append("isbn10 = ?")
                    params.append(book.isbn10)
                if book.isbn13:
                    clauses.append("isbn13 = ?")
                    params.append(book.isbn13)
                where = " OR ".join(clauses)
                rows = conn.execute(f"SELECT * FROM books WHERE {where}", params).fetchall()
                candidates.extend(rows)

            title = normalize_text(book.title)
            if title:
                rows = conn.execute(
                    "SELECT * FROM books WHERE title = ?",
                    (title,),
                ).fetchall()
                author_keys = {normalize_text(author).casefold() for author in book.authors}
                for row in rows:
                    row_authors = {
                        normalize_text(author).casefold()
                        for author in json.loads(row["authors_json"] or "[]")
                    }
                    if not author_keys or not row_authors or author_keys & row_authors:
                        candidates.append(row)

        unique: dict[str, sqlite3.Row] = {}
        for row in candidates:
            if exclude_id is not None and row["id"] == exclude_id:
                continue
            unique[row["id"]] = row
        return list(unique.values())

    def delete(self, book_id: str) -> bool:
        with transaction(self.db) as conn:
            result = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            return result.rowcount == 1


    def add_reading_session(self, session_id: str, book_id: str, started_at: str, minutes: int, pages: int, note: str | None = None) -> None:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO reading_sessions(id,book_id,started_at,minutes,pages,note) VALUES(?,?,?,?,?,?)", (session_id, book_id, started_at, minutes, pages, note))

    def list_reading_sessions(self, book_id: str, limit: int = 100) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM reading_sessions WHERE book_id=? ORDER BY started_at DESC LIMIT ?", (book_id, limit)).fetchall()

    def add_note(self, note_id: str, book_id: str, text: str, page: int | None = None) -> None:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO notes(id,book_id,text,page) VALUES(?,?,?,?)", (note_id, book_id, text, page))

    def add_quote(self, quote_id: str, book_id: str, text: str, page: int | None = None, source: str | None = None) -> None:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO quotes(id,book_id,text,page,source) VALUES(?,?,?,?,?)", (quote_id, book_id, text, page, source))

    def list_knowledge(self, book_id: str) -> dict[str, list[sqlite3.Row]]:
        with self.db.connect() as conn:
            return {"notes": conn.execute("SELECT * FROM notes WHERE book_id=? ORDER BY created_at DESC", (book_id,)).fetchall(), "quotes": conn.execute("SELECT * FROM quotes WHERE book_id=? ORDER BY created_at DESC", (book_id,)).fetchall()}

    def add_copy(self, copy_id: str, book_id: str, condition: str = "good", status: str = "available", internal_code: str | None = None) -> None:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO physical_copies(id,book_id,condition,status,internal_code) VALUES(?,?,?,?,?)", (copy_id, book_id, condition, status, internal_code))

    def add_loan(self, loan_id: str, copy_id: str, borrower_id: str, loaned_on: str, due_on: str | None = None, notes: str | None = None) -> None:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO loans(id,copy_id,borrower_id,loaned_on,due_on,notes) VALUES(?,?,?,?,?,?)", (loan_id, copy_id, borrower_id, loaned_on, due_on, notes))

    def list_loans(self, limit: int = 100) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM loans ORDER BY loaned_on DESC LIMIT ?", (limit,)).fetchall()


    def add_audiobook(
        self,
        audiobook_id: str,
        book_id: str,
        path: str,
        audio_format: str,
        duration_seconds: int,
    ) -> str:
        if not path.strip():
            raise ValueError("audio path is required")
        if duration_seconds < 0:
            raise ValueError("audio duration must be non-negative")
        if not audio_format.strip():
            raise ValueError("audio format is required")
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
                raise ValueError("book not found")
            conn.execute(
                """INSERT INTO audiobooks
                   (id, book_id, path, format, duration_seconds)
                   VALUES (?, ?, ?, ?, ?)""",
                (audiobook_id, book_id, path.strip(), audio_format.lower().strip(), duration_seconds),
            )
        return audiobook_id

    def get_audiobook(self, audiobook_id: str) -> sqlite3.Row | None:
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM audiobooks WHERE id = ?", (audiobook_id,)
            ).fetchone()

    def list_audiobooks(self, book_id: str) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM audiobooks WHERE book_id = ? ORDER BY id", (book_id,)
            ).fetchall()

    def update_audiobook_progress(
        self,
        audiobook_id: str,
        *,
        position_seconds: int,
        speed: float = 1.0,
    ) -> bool:
        if position_seconds < 0:
            raise ValueError("audio position must be non-negative")
        if speed <= 0:
            raise ValueError("audio speed must be positive")
        with transaction(self.db) as conn:
            row = conn.execute(
                "SELECT duration_seconds FROM audiobooks WHERE id = ?",
                (audiobook_id,),
            ).fetchone()
            if row is None:
                raise ValueError("audiobook not found")
            if position_seconds > row["duration_seconds"]:
                raise ValueError("audio position exceeds duration")
            result = conn.execute(
                """UPDATE audiobooks
                   SET position_seconds = ?, speed = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (position_seconds, speed, audiobook_id),
            )
            return result.rowcount == 1


    def add_annotation(self, annotation_id: str, book_id: str, kind: str, locator: str, text: str | None = None, note: str | None = None) -> None:
        from .digital import Annotation
        Annotation(book_id, kind, locator, text, note)
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
                raise ValueError("book not found")
            conn.execute("INSERT INTO annotations(id,book_id,kind,locator,text,note) VALUES(?,?,?,?,?,?)", (annotation_id, book_id, kind, locator.strip(), text, note))

    def list_annotations(self, book_id: str, limit: int = 500) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM annotations WHERE book_id = ? ORDER BY created_at DESC LIMIT ?", (book_id, limit)).fetchall()
