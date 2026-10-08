import json
import sqlite3

import pytest

from books.db import BookRepository, Database


def book(book_id="b1"):
    return {
        "id": book_id,
        "title": "کتاب نمونه",
        "original_title": None,
        "authors_json": json.dumps(["نویسنده"], ensure_ascii=False),
        "translators_json": "[]",
        "publisher": "ناشر",
        "pages": 120,
        "publication_year": 1400,
        "isbn10": None,
        "isbn13": "9786000000000",
        "language": "fa",
        "genres_json": "[]",
        "subjects_json": "[]",
        "summary": None,
        "cover_url": None,
        "source_ids_json": "{}",
        "notes": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def test_migration_is_idempotent(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 11
    assert db.migrate() == 0
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0] == 11


def test_repository_crud_and_persistence(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)

    assert repo.create(book()) == "b1"
    row = repo.get("b1")
    assert row["title"] == "کتاب نمونه"
    assert len(repo.list()) == 1
    assert repo.delete("b1") is True
    assert repo.get("b1") is None
    assert repo.delete("missing") is False


def test_duplicate_isbn_is_rejected(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create(book("b1"))
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(book("b2"))


def test_migrate_hardens_database_file_permissions(tmp_path):
    import os

    db_path = tmp_path / "books.sqlite3"
    Database(db_path).migrate()
    assert os.stat(db_path).st_mode & 0o777 == 0o600


def test_get_by_isbn_finds_hyphenated_and_persian_digits(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create(book("b1"))
    assert repo.get_by_isbn("978-600-000-000-0")["id"] == "b1"
    assert repo.get_by_isbn("۹۷۸۶۰۰۰۰۰۰۰۰۰")["id"] == "b1"
    assert repo.get_by_isbn("  9786000000000  ")["id"] == "b1"
    assert repo.get_by_isbn("") is None


def test_search_matches_genre_subject_summary_notes(tmp_path):
    import json as _json
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    row = book("b1")
    row["genres_json"] = _json.dumps(["فانتزی"], ensure_ascii=False)
    row["subjects_json"] = _json.dumps(["جادو"], ensure_ascii=False)
    row["summary"] = "ماجرای یک حلقه"
    row["notes"] = "یادداشت شخصی درباره سفر"
    repo.create(row)
    assert [r["id"] for r in repo.search("فانتزی")] == ["b1"]
    assert [r["id"] for r in repo.search("جادو")] == ["b1"]
    assert [r["id"] for r in repo.search("حلقه")] == ["b1"]
    assert [r["id"] for r in repo.search("سفر")] == ["b1"]
