from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .db import BookRepository, transaction
from .models import Book

SCHEMA_VERSION = 2
# Version 1 payloads (books/personal/tags/shelves only) must keep importing.
SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2})

# Related-record domains included in the portable JSON format (schema v2):
# key -> (table, columns, key columns, reference table, reference column).
# Order matters: book-referenced rows come after the books loop, physical
# copies before loans, knowledge nodes before edges. Table and column names
# are a fixed allow-list — never taken from the payload.
EXTRA_DOMAINS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], str | None, str | None]] = {
    "reading_sessions": ("reading_sessions", ("id", "book_id", "started_at", "minutes", "pages", "note"), ("id",), "books", "book_id"),
    "reading_goals": ("reading_goals", ("id", "target_books", "target_pages", "start_date", "end_date"), ("id",), None, None),
    "notes": ("notes", ("id", "book_id", "text", "page", "created_at"), ("id",), "books", "book_id"),
    "quotes": ("quotes", ("id", "book_id", "text", "page", "source", "created_at"), ("id",), "books", "book_id"),
    "physical_copies": ("physical_copies", ("id", "book_id", "condition", "status", "internal_code"), ("id",), "books", "book_id"),
    "loans": ("loans", ("id", "copy_id", "borrower_id", "loaned_on", "due_on", "returned_on", "notes"), ("id",), "physical_copies", "copy_id"),
    "audiobooks": ("audiobooks", ("id", "book_id", "path", "format", "duration_seconds", "position_seconds", "speed", "created_at", "updated_at"), ("id",), "books", "book_id"),
    "annotations": ("annotations", ("id", "book_id", "kind", "locator", "text", "note", "created_at", "updated_at"), ("id",), "books", "book_id"),
    "knowledge_nodes": ("knowledge_nodes", ("id", "label", "kind"), ("id",), None, None),
    "knowledge_edges": ("knowledge_edges", ("source_id", "target_id", "relation"), ("source_id", "target_id", "relation"), "knowledge_nodes", "source_id"),
}

_EXTRA_INT_COLUMNS = frozenset(
    {"minutes", "pages", "target_books", "target_pages", "page", "duration_seconds", "position_seconds"}
)


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Outcome of an import run.

    ``imported`` counts newly created books, ``updated`` counts rows matched by
    their exported id and written back, and ``skipped`` records every row that
    was not applied together with a human-readable reason, so a re-import never
    fails silently.
    """

    imported: int = 0
    updated: int = 0
    skipped: tuple[tuple[str, str], ...] = ()
    extras: tuple[tuple[str, int], ...] = ()

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def extra_count(self) -> int:
        """Rows imported across the related-record domains (schema v2)."""
        return sum(count for _domain, count in self.extras)

    def __int__(self) -> int:
        return self.imported + self.updated


class BookTransferService:
    """Schema-versioned JSON/CSV transfer with explicit merge/update imports."""

    CSV_FIELDS = (
        "id", "title", "original_title", "authors", "translators", "publisher",
        "pages", "publication_year", "isbn10", "isbn13", "language", "genres",
        "subjects", "summary", "cover_url", "source_ids", "notes",
        "reading_status", "reading_current_page", "reading_progress",
        "reading_started_at", "reading_finished_at", "rating", "note", "quote",
        "favorite", "tags", "shelves",
    )

    def __init__(self, repository: BookRepository) -> None:
        self.repository = repository

    def export_json(self) -> str:
        snapshot = self._snapshot()
        return json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                **snapshot,
            },
            ensure_ascii=False,
            indent=2,
        )

    def export_csv(self) -> str:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=self.CSV_FIELDS)
        writer.writeheader()
        for row in self._rows():
            writer.writerow(self._csv_row(row))
        return output.getvalue()

    def import_json(self, payload: str) -> ImportReport:
        data = self._parse_json(payload)
        return self._import_snapshot(data)

    def import_csv(self, payload: str) -> ImportReport:
        if len(payload.encode("utf-8")) > 10 * 1024 * 1024:
            raise ValueError("import payload exceeds 10 MiB")
        stream = io.StringIO(payload, newline="")
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != self.CSV_FIELDS:
            raise ValueError("unsupported CSV schema")
        imported = updated = 0
        skipped: list[tuple[str, str]] = []
        for row in reader:
            row_imported, row_updated, row_skipped = self._import_book_row(
                self._book_row_from_csv(row)
            )
            imported += row_imported
            updated += row_updated
            skipped.extend(row_skipped)
        return ImportReport(imported, updated, tuple(skipped))

    def _snapshot(self) -> dict[str, Any]:
        with self.repository.db.connect() as conn:
            books = [dict(row) for row in conn.execute("SELECT * FROM books ORDER BY id")]
            personal = [dict(row) for row in conn.execute("SELECT * FROM book_personal ORDER BY book_id")]
            tags = [dict(row) for row in conn.execute("SELECT * FROM tags ORDER BY id")]
            shelves = [dict(row) for row in conn.execute("SELECT * FROM shelves ORDER BY id")]
            book_tags = [dict(row) for row in conn.execute("SELECT * FROM book_tags ORDER BY book_id, tag_id")]
            book_shelves = [dict(row) for row in conn.execute("SELECT * FROM book_shelves ORDER BY book_id, shelf_id")]
            extras: dict[str, list[dict[str, Any]]] = {}
            for key, (table, _columns, key_columns, _ref_table, _ref_column) in EXTRA_DOMAINS.items():
                order = ", ".join(key_columns)
                extras[key] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}")]
        return {
            "books": books,
            "book_personal": personal,
            "tags": tags,
            "shelves": shelves,
            "book_tags": book_tags,
            "book_shelves": book_shelves,
            **extras,
        }

    def _rows(self) -> list[dict[str, Any]]:
        snapshot = self._snapshot()
        personal = {row["book_id"]: row for row in snapshot["book_personal"]}
        tags = {row["id"]: row["name"] for row in snapshot["tags"]}
        shelves = {row["id"]: row["name"] for row in snapshot["shelves"]}
        tag_map: dict[str, list[str]] = {}
        shelf_map: dict[str, list[str]] = {}
        for relation in snapshot["book_tags"]:
            tag_map.setdefault(relation["book_id"], []).append(tags[relation["tag_id"]])
        for relation in snapshot["book_shelves"]:
            shelf_map.setdefault(relation["book_id"], []).append(shelves[relation["shelf_id"]])

        rows = []
        for book in snapshot["books"]:
            p = personal.get(book["id"], {})
            row = dict(book)
            row.update(
                rating=p.get("rating"),
                note=p.get("note"),
                quote=p.get("quote"),
                favorite=p.get("favorite", 0),
                # JSON arrays keep multi-value cells intact: a value that itself
                # contains "|" can no longer be split apart on import.
                tags=json.dumps(tag_map.get(book["id"], ()), ensure_ascii=False),
                shelves=json.dumps(shelf_map.get(book["id"], ()), ensure_ascii=False),
            )
            rows.append(row)
        return rows

    def _csv_row(self, row: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in self.CSV_FIELDS:
            value = row.get(field)
            if field in {
                "authors", "translators", "genres", "subjects", "source_ids"
            }:
                key = f"{field}_json"
                if key in row:
                    value = row[key]
                elif field == "source_ids":
                    value = json.dumps(value or {}, ensure_ascii=False)
            result[field] = "" if value is None else str(value)
        return result

    @staticmethod
    def _parse_json(payload: str) -> dict[str, Any]:
        if len(payload.encode("utf-8")) > 10 * 1024 * 1024:
            raise ValueError("import payload exceeds 10 MiB")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON") from exc
        if not isinstance(data, dict) or data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError("unsupported JSON schema version")
        return data

    def _import_snapshot(self, data: dict[str, Any]) -> ImportReport:
        books = data.get("books")
        if not isinstance(books, list):
            raise TypeError("JSON books must be a list")
        personal = {
            row["book_id"]: row
            for row in data.get("book_personal", [])
            if isinstance(row, dict) and row.get("book_id")
        }
        tags = {
            row["id"]: row["name"]
            for row in data.get("tags", [])
            if isinstance(row, dict) and row.get("id") and row.get("name")
        }
        shelves = {
            row["id"]: row["name"]
            for row in data.get("shelves", [])
            if isinstance(row, dict) and row.get("id") and row.get("name")
        }
        tag_map: dict[str, list[str]] = {}
        shelf_map: dict[str, list[str]] = {}
        for relation in data.get("book_tags", []):
            if isinstance(relation, dict) and relation.get("book_id") and relation.get("tag_id") in tags:
                tag_map.setdefault(relation["book_id"], []).append(tags[relation["tag_id"]])
        for relation in data.get("book_shelves", []):
            if isinstance(relation, dict) and relation.get("book_id") and relation.get("shelf_id") in shelves:
                shelf_map.setdefault(relation["book_id"], []).append(shelves[relation["shelf_id"]])

        imported = updated = 0
        skipped: list[tuple[str, str]] = []
        for row in books:
            if not isinstance(row, dict):
                raise TypeError("invalid book row")
            enriched = dict(row)
            book_key = str(row.get("id"))
            p = personal.get(book_key, {})
            enriched.update(
                rating=p.get("rating"),
                note=p.get("note"),
                quote=p.get("quote"),
                favorite=p.get("favorite", 0),
                tags=tag_map.get(book_key, ()),
                shelves=shelf_map.get(book_key, ()),
                # Preserve exported identifiers so tags/shelves keep their ids
                # across an export -> import round-trip.
                tag_ids=self._relation_ids(data.get("book_tags", []), book_key, "tag_id", tags),
                shelf_ids=self._relation_ids(data.get("book_shelves", []), book_key, "shelf_id", shelves),
            )
            row_imported, row_updated, row_skipped = self._import_book_row(enriched)
            imported += row_imported
            updated += row_updated
            skipped.extend(row_skipped)
        extras = self._apply_extra_domains(data, skipped)
        return ImportReport(imported, updated, tuple(skipped), extras)

    def _apply_extra_domains(
        self,
        data: dict[str, Any],
        skipped: list[tuple[str, str]],
    ) -> tuple[tuple[str, int], ...]:
        """Insert the related-record domains; merge-only and idempotent.

        Rows are keyed by their exported identifiers: a row whose id already
        exists is left untouched (a re-import is a no-op, never a duplicate),
        and rows referencing a missing book/copy/node are skipped with a
        visible reason instead of failing silently.
        """
        counts: list[tuple[str, int]] = []
        db = self.repository.db
        for key, (table, columns, key_columns, ref_table, ref_column) in EXTRA_DOMAINS.items():
            rows = data.get(key) or []
            if not isinstance(rows, list):
                raise TypeError(f"JSON {key} must be a list")
            imported = 0
            with transaction(db) as conn:
                for row in rows:
                    if not isinstance(row, dict):
                        raise TypeError(f"invalid {key} row")
                    values = self._extra_values(row, columns)
                    if any(values[column] in (None, "") for column in key_columns):
                        skipped.append(("", f"{key}: row without an identifier"))
                        continue
                    identity = " AND ".join(f"{column} = ?" for column in key_columns)
                    parameters = tuple(values[column] for column in key_columns)
                    if conn.execute(f"SELECT 1 FROM {table} WHERE {identity}", parameters).fetchone():
                        continue  # already present: idempotent re-import
                    if ref_table is not None:
                        reference = values[ref_column]
                        found = conn.execute(
                            f"SELECT 1 FROM {ref_table} WHERE id = ?", (reference,)
                        ).fetchone()
                        if found is None:
                            skipped.append(
                                (
                                    str(values[key_columns[0]]),
                                    f"{key}: {ref_column} {reference} not found",
                                )
                            )
                            continue
                    insert_columns = tuple(
                        column for column in columns if values[column] is not None
                    )
                    placeholders = ", ".join("?" for _column in insert_columns)
                    conn.execute(
                        f"INSERT INTO {table} ({', '.join(insert_columns)}) VALUES ({placeholders})",
                        tuple(values[column] for column in insert_columns),
                    )
                    imported += 1
            if imported:
                counts.append((key, imported))
        return tuple(counts)

    @staticmethod
    def _extra_values(row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for column in columns:
            value = row.get(column)
            if column in _EXTRA_INT_COLUMNS and value not in (None, ""):
                value = int(value)
            elif column == "speed" and value not in (None, ""):
                value = float(value)
            values[column] = value
        return values

    def _import_book_row(self, row: dict[str, Any]) -> tuple[int, int, tuple[tuple[str, str], ...]]:
        """Apply one row.

        Returns ``(imported, updated, skipped)`` where each skipped entry is a
        ``(book_id, reason)`` pair, so callers can always explain what was not
        applied instead of silently reporting zero.
        """
        title = str(row.get("title") or "").strip()
        if not title:
            raise ValueError("book title is required")
        book = Book(
            title=title,
            original_title=row.get("original_title"),
            authors=self._tuple_value(row.get("authors_json") or row.get("authors")),
            translators=self._tuple_value(row.get("translators_json") or row.get("translators")),
            publisher=row.get("publisher"),
            pages=self._int_value(row.get("pages")),
            publication_year=self._int_value(row.get("publication_year")),
            isbn10=row.get("isbn10") or None,
            isbn13=row.get("isbn13") or None,
            language=row.get("language"),
            genres=self._tuple_value(row.get("genres_json") or row.get("genres")),
            subjects=self._tuple_value(row.get("subjects_json") or row.get("subjects")),
            summary=row.get("summary"),
            cover_url=row.get("cover_url"),
            source_ids=self._mapping_value(row.get("source_ids_json") or row.get("source_ids")),
            notes=row.get("notes"),
        )

        row_id = str(row["id"]) if row.get("id") else None
        existing = self.repository.get(row_id) if row_id else None
        duplicates = self.repository.find_duplicates(book, exclude_id=row_id)

        if existing is not None:
            # Matched by exported id: re-importing a corrected file is an update.
            self.repository.update_book(str(existing["id"]), book)
            self._apply_row_state(str(existing["id"]), row)
            return 0, 1, ()

        if duplicates:
            matched = str(duplicates[0]["id"])
            reason = f"duplicate of existing book {matched}"
            if row_id:
                self.repository.create_book(book, row_id)
                self._apply_row_state(row_id, row)
                return 1, 0, ()
            return 0, 0, ((matched, reason),)

        book_id = self.repository.create_book(book, row_id)
        self._apply_row_state(book_id, row)
        return 1, 0, ()

    def _apply_row_state(self, book_id: str, row: dict[str, Any]) -> None:
        if row.get("reading_status"):
            self.repository.update_reading_status(book_id, str(row["reading_status"]))
        current_page = self._int_value(row.get("reading_current_page"))
        if current_page and row.get("pages") not in (None, "", 0, "0"):
            self.repository.update_reading_progress(book_id, current_page)

        started_at = row.get("reading_started_at") or None
        finished_at = row.get("reading_finished_at") or None
        if started_at or finished_at:
            self.repository.update_reading_dates(
                book_id,
                started_at=started_at,
                finished_at=finished_at,
            )

        rating = self._int_value(row.get("rating"))
        if rating is not None or row.get("note") or row.get("quote"):
            self.repository.update_personal_data(
                book_id,
                rating=rating,
                note=str(row.get("note") or ""),
                quote=str(row.get("quote") or ""),
            )
        if row.get("favorite") in (1, "1", True, "true"):
            self.repository.update_favorite(book_id, True)

        tags = self._tuple_value(row.get("tags"))
        shelves = self._tuple_value(row.get("shelves"))
        if tags or shelves:
            self.repository.set_organization(
                book_id,
                tags=tags,
                shelves=shelves,
                tag_ids=self._id_map(row.get("tag_ids")),
                shelf_ids=self._id_map(row.get("shelf_ids")),
            )

    @staticmethod
    def _relation_ids(
        relations: list[Any],
        book_key: str,
        id_field: str,
        names: dict[str, str],
    ) -> dict[str, str]:
        """Map ``name -> exported id`` for one book's relations."""
        mapping: dict[str, str] = {}
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            if str(relation.get("book_id")) != book_key:
                continue
            identifier = relation.get(id_field)
            if identifier in names:
                mapping[names[identifier]] = str(identifier)
        return mapping

    @staticmethod
    def _id_map(value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict) or not value:
            return None
        return {str(name): str(identifier) for name, identifier in value.items()}

    def _book_row_from_csv(self, row: dict[str, str]) -> dict[str, Any]:
        result = dict(row)
        for field in ("authors", "translators", "genres", "subjects", "tags", "shelves"):
            # Accept both the current JSON-array encoding and legacy "|"-joined
            # values so previously exported files keep importing unchanged.
            result[field] = self._tuple_value(row.get(field))
        result["source_ids"] = row.get("source_ids") or "{}"
        return result

    @staticmethod
    def _tuple_value(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (tuple, list)):
            return tuple(str(item) for item in value if str(item).strip())
        text = str(value)
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return tuple(str(item) for item in parsed if str(item).strip())
            except json.JSONDecodeError:
                pass
        return tuple(item.strip() for item in text.split("|") if item.strip())

    @staticmethod
    def _mapping_value(value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return {}
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}

    @staticmethod
    def _int_value(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)
