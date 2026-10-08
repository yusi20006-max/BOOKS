import sqlite3

from books.db import Database
from books.health import expected_tables, main, missing_tables, validate_database


def test_health_check_accepts_initialized_database(tmp_path, monkeypatch):
    db_path = tmp_path / "books.sqlite3"
    Database(db_path).migrate()
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    assert main() == 0


def test_expected_tables_derive_from_migrations(tmp_path):
    tables = expected_tables()
    assert {"books", "schema_migrations", "reading_sessions", "notes", "quotes", "loans", "annotations", "tags", "shelves", "book_tags", "book_shelves", "physical_copies", "audiobooks", "knowledge_nodes", "sync_changes"}.issubset(tables)
    db_path = tmp_path / "books.sqlite3"
    Database(db_path).migrate()
    with Database(db_path).connect() as conn:
        assert not missing_tables(conn)


def test_books_only_database_is_rejected(tmp_path, monkeypatch):
    db_path = tmp_path / "truncated.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE books (id TEXT PRIMARY KEY, title TEXT)")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    assert main() == 1

    with Database(db_path).connect() as check:
        absent = missing_tables(check)
    assert "reading_sessions" in absent and "loans" in absent

    try:
        validate_database(db_path)
    except ValueError as exc:
        assert "reading_sessions" in str(exc)
    else:
        raise AssertionError("truncated database must fail validation")
