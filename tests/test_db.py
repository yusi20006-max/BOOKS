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


def test_migration_trees_do_not_diverge():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    packaged = root / "src" / "books" / "migrations"
    working = root / "migrations"
    assert packaged.is_dir() and working.is_dir()

    def snapshot(directory):
        return {
            path.name: path.read_bytes()
            for path in directory.glob("[0-9][0-9][0-9]_*.sql")
        }

    assert snapshot(packaged) == snapshot(working), (
        "migrations/ and src/books/migrations/ must stay byte-identical "
        "(issue #336): copy every change to both trees"
    )


def test_migration_drift_guard_raises(tmp_path):
    from books.db import _assert_migration_trees_match

    packaged = tmp_path / "packaged"
    tree = tmp_path / "root"
    packaged.mkdir()
    tree.mkdir()
    (packaged / "001_same.sql").write_text("SELECT 1;", encoding="utf-8")
    (tree / "001_same.sql").write_text("SELECT 1;", encoding="utf-8")
    _assert_migration_trees_match(packaged, tree)  # identical: no raise

    (tree / "001_same.sql").write_text("SELECT 2;", encoding="utf-8")
    (tree / "002_only_root.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(RuntimeError, match="diverged"):
        _assert_migration_trees_match(packaged, tree)


def test_new_file_with_applied_version_prefix_is_applied_once(tmp_path, monkeypatch):
    tree = tmp_path / "migrations"
    tree.mkdir()
    (tree / "001_one.sql").write_text(
        "CREATE TABLE IF NOT EXISTS one(id TEXT);", encoding="utf-8"
    )
    (tree / "002_two.sql").write_text(
        "CREATE TABLE IF NOT EXISTS two(id TEXT);", encoding="utf-8"
    )
    monkeypatch.setattr("books.db._resolve_migrations_dir", lambda: tree)

    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 2
    assert db.migrate() == 0

    # A file added later under an already-applied prefix must still run — once.
    (tree / "002_extra.sql").write_text(
        "CREATE TABLE IF NOT EXISTS extra(id TEXT);", encoding="utf-8"
    )
    assert db.migrate() == 1
    assert db.migrate() == 0

    with db.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        ledger = conn.execute(
            "SELECT name FROM schema_migrations WHERE version = 2"
        ).fetchone()["name"]
    assert {"one", "two", "extra"} <= tables
    assert set(ledger.split(", ")) == {"002_two.sql", "002_extra.sql"}


def test_interrupted_group_resumes_without_rerunning_recorded_files(tmp_path, monkeypatch):
    tree = tmp_path / "migrations"
    tree.mkdir()
    # Re-running 002_two.sql would add a second row — the marker of a re-run.
    (tree / "002_two.sql").write_text(
        "CREATE TABLE IF NOT EXISTS two(id TEXT); INSERT INTO two VALUES ('x');",
        encoding="utf-8",
    )
    (tree / "002_three.sql").write_text(
        "CREATE TABLE IF NOT EXISTS three(id TEXT);", encoding="utf-8"
    )
    monkeypatch.setattr("books.db._resolve_migrations_dir", lambda: tree)

    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 1
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM two").fetchone()[0] == 1

    # Simulate a crash after 002_two was applied and recorded but before
    # 002_three ran: only the recorded file is in the ledger and the table it
    # creates is absent.
    with db.connect() as conn:
        conn.execute(
            "UPDATE schema_migrations SET name = '002_two.sql' WHERE version = 2"
        )
        conn.execute("DROP TABLE three")

    assert db.migrate() == 1  # resumes: applies only the missing file
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM two").fetchone()[0] == 1  # not re-run
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name = 'three'"
        ).fetchone()[0] == 1
        ledger = conn.execute(
            "SELECT name FROM schema_migrations WHERE version = 2"
        ).fetchone()["name"]
    assert set(ledger.split(", ")) == {"002_two.sql", "002_three.sql"}
    assert db.migrate() == 0
