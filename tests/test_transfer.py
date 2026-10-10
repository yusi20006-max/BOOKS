import csv
import io
import json

import pytest

from books.db import BookRepository, Database
from books.models import Book
from books.transfer import BookTransferService


def test_json_round_trip_preserves_core_and_personal_data(tmp_path):
    db = Database(tmp_path / "source.sqlite3")
    assert db.migrate() == 11
    repository = BookRepository(db)
    book_id = repository.create_book(
        Book(
            title="شازده کوچولو",
            authors=("آنتوان دو سنت اگزوپری",),
            pages=100,
            isbn13="9780156012195",
            publisher="ناشر",
        )
    )
    repository.update_reading_status(book_id, "reading")
    repository.update_reading_progress(book_id, 25)
    repository.update_personal_data(
        book_id,
        rating=5,
        note="یادداشت من",
        quote="نقل‌قول",
    )
    repository.set_organization(book_id, tags=("فارسی",), shelves=("مطالعه",))

    payload = BookTransferService(repository).export_json()

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookTransferService(BookRepository(target_db))
    assert int(target.import_json(payload)) == 1

    target_repo = BookRepository(target_db)
    row = target_repo.list()[0]
    assert row["title"] == "شازده کوچولو"
    assert row["reading_status"] == "reading"
    assert row["reading_progress"] == 25
    personal = target_repo.get_personal_data(book_id)
    assert personal["rating"] == 5
    assert target_repo.get_organization(book_id) == (("فارسی",), ("مطالعه",))


def test_csv_round_trip_preserves_persian_metadata(tmp_path):
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    source = BookRepository(source_db)
    source.create_book(Book(title="کتاب فارسی", authors=("نویسنده",), isbn13="9780156012195"))
    payload = BookTransferService(source).export_csv()

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookTransferService(BookRepository(target_db))
    assert int(target.import_csv(payload)) == 1
    assert BookRepository(target_db).list()[0]["title"] == "کتاب فارسی"


def test_reimport_with_edits_updates_instead_of_silently_skipping(tmp_path):
    """Re-importing a corrected file must apply edits, not report a silent zero."""
    db = Database(tmp_path / "source.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="عنوان قدیمی", pages=100))
    service = BookTransferService(repo)

    data = json.loads(service.export_json())
    data["books"][0]["title"] = "عنوان ویرایش‌شده"
    data["books"][0]["pages"] = 200
    data["books"][0]["summary"] = "خلاصه تازه"

    report = service.import_json(json.dumps(data, ensure_ascii=False))

    assert report.imported == 0
    assert report.updated == 1
    row = repo.get(book_id)
    assert row["title"] == "عنوان ویرایش‌شده"
    assert row["pages"] == 200
    assert row["summary"] == "خلاصه تازه"


def _first_id(payload: str) -> str:
    """Return the id cell of the first CSV data row."""
    rows = list(csv.DictReader(io.StringIO(payload, newline="")))
    return rows[0]["id"]


def test_duplicate_row_is_skipped_with_visible_reason(tmp_path):
    """A duplicate that cannot be matched by id is reported, never silent."""
    db = Database(tmp_path / "source.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create_book(Book(title="کتاب یکتا", authors=("نویسنده",)))
    service = BookTransferService(repo)

    # A row with no exported id cannot be matched, so it must be reported as a
    # skipped duplicate rather than silently dropped.
    payload = service.export_csv()
    payload = payload.replace(_first_id(payload), "")
    report = service.import_csv(payload)

    assert report.imported == 0
    assert report.updated == 0
    assert report.skipped_count == 1
    book_id, reason = report.skipped[0]
    assert "duplicate" in reason
    assert book_id


def test_tag_and_shelf_ids_are_stable_across_export_import(tmp_path):
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    source = BookRepository(source_db)
    book_id = source.create_book(Book(title="کتاب"))
    source.set_organization(book_id, tags=("فارسی",), shelves=("مطالعه",))

    original_tags = {
        row["name"]: row["id"]
        for row in source_db.connect().execute("SELECT id, name FROM tags")
    }
    original_shelves = {
        row["name"]: row["id"]
        for row in source_db.connect().execute("SELECT id, name FROM shelves")
    }
    payload = BookTransferService(source).export_json()

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookRepository(target_db)
    BookTransferService(target).import_json(payload)

    imported_tags = {
        row["name"]: row["id"] for row in target_db.connect().execute("SELECT id, name FROM tags")
    }
    imported_shelves = {
        row["name"]: row["id"]
        for row in target_db.connect().execute("SELECT id, name FROM shelves")
    }

    assert imported_tags == original_tags
    assert imported_shelves == original_shelves


def test_values_containing_pipe_survive_csv_round_trip(tmp_path):
    """A value containing the legacy delimiter must not be split or corrupted."""
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    source = BookRepository(source_db)
    source.create_book(
        Book(
            title="کتاب لوله‌ای",
            authors=("نویسنده|دوم",),
            genres=("فانتزی|ماجراجویی",),
            subjects=("الف|ب",),
        )
    )
    source.set_organization(
        source.list()[0]["id"], tags=("برچسب|ویژه",), shelves=("قفسه|من",)
    )

    payload = BookTransferService(source).export_csv()

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookRepository(target_db)
    assert int(BookTransferService(target).import_csv(payload)) == 1

    row = target.list()[0]
    assert json.loads(row["authors_json"]) == ["نویسنده|دوم"]
    assert json.loads(row["genres_json"]) == ["فانتزی|ماجراجویی"]
    assert json.loads(row["subjects_json"]) == ["الف|ب"]
    assert target.get_organization(row["id"]) == (
        ("برچسب|ویژه",),
        ("قفسه|من",),
    )


def test_legacy_pipe_joined_csv_still_imports(tmp_path):
    """Exports written before the JSON-array change must remain importable."""
    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    service = BookTransferService(BookRepository(target_db))
    row = {field: "" for field in service.CSV_FIELDS}
    row.update(
        {
            "id": "legacy-1",
            "title": "کتاب قدیمی",
            "authors": "نویسنده|مترجم",
            "genres": "فانتزی",
            "tags": "برچسب",
            "shelves": "قفسه",
        }
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=service.CSV_FIELDS)
    writer.writeheader()
    writer.writerow(row)

    assert int(service.import_csv(buffer.getvalue())) == 1
    imported = BookRepository(target_db).list()[0]
    assert json.loads(imported["authors_json"]) == ["نویسنده", "مترجم"]
    assert BookRepository(target_db).get_organization("legacy-1") == (
        ("برچسب",),
        ("قفسه",),
    )


def test_progress_and_dates_persist_through_validated_writes(tmp_path):
    db = Database(tmp_path / "source.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="کتاب", pages=300))
    service = BookTransferService(repo)

    data = json.loads(service.export_json())
    data["books"][0]["reading_status"] = "finished"
    data["books"][0]["reading_current_page"] = 150
    data["books"][0]["reading_started_at"] = "2026-01-01T10:00:00+00:00"
    data["books"][0]["reading_finished_at"] = "2026-01-05T10:00:00+00:00"

    assert int(service.import_json(json.dumps(data, ensure_ascii=False))) == 1

    row = repo.get(book_id)
    assert row["reading_status"] == "finished"
    assert row["reading_current_page"] == 150
    assert row["reading_progress"] == 50
    assert row["reading_started_at"] == "2026-01-01T10:00:00+00:00"
    assert row["reading_finished_at"] == "2026-01-05T10:00:00+00:00"


def test_reversed_reading_dates_are_rejected(tmp_path):
    db = Database(tmp_path / "source.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="کتاب"))
    with pytest.raises(ValueError):
        repo.update_reading_dates(
            book_id,
            started_at="2026-01-05T10:00:00+00:00",
            finished_at="2026-01-01T10:00:00+00:00",
        )
    with pytest.raises(ValueError):
        repo.update_reading_dates(book_id, started_at=None, finished_at=None)


def test_json_round_trip_covers_all_related_domains(tmp_path):
    from datetime import date

    from books.knowledge import KnowledgeEdge, KnowledgeNode
    from books.knowledge_store import KnowledgeStore
    from books.reading_journal import ReadingGoal
    from books.reading_journal_store import ReadingJournalStore

    expected_counts = {
        "reading_sessions": 1,
        "reading_goals": 1,
        "notes": 1,
        "quotes": 1,
        "knowledge_nodes": 2,
        "knowledge_edges": 1,
        "physical_copies": 1,
        "loans": 1,
        "audiobooks": 1,
        "annotations": 1,
    }

    source_db = Database(tmp_path / "source.sqlite3")
    assert source_db.migrate() == 11
    repository = BookRepository(source_db)
    book_id = repository.create_book(
        Book(title="کتاب جامع", authors=("نویسنده",), pages=200)
    )
    repository.add_reading_session("session-1", book_id, "2026-09-27", 45, 12, "یادداشت جلسه")
    repository.add_note("note-1", book_id, "یادداشت متنی", 5)
    repository.add_quote("quote-1", book_id, "نقل‌قول", 9, "صفحه ۹")
    repository.add_copy("copy-1", book_id, internal_code="BK-001")
    repository.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-27", "2026-10-27")
    repository.add_audiobook("audiobook-1", book_id, "/tmp/audio.mp3", "mp3", 120)
    repository.add_annotation("ann-1", book_id, "bookmark", "loc-1", "متن", "یادداشت حاشیه")
    ReadingJournalStore(source_db).add_goal(
        ReadingGoal("goal-1", 2, 200, date(2026, 9, 1), date(2026, 10, 1))
    )
    store = KnowledgeStore(source_db)
    store.add_node(KnowledgeNode("node-1", "مفهوم اول"))
    store.add_node(KnowledgeNode("node-2", "مفهوم دوم"))
    store.add_edge(KnowledgeEdge("node-1", "node-2", "مرتبط"))

    payload = BookTransferService(repository).export_json()
    data = json.loads(payload)
    assert data["schema_version"] == 2
    assert {key: len(data[key]) for key in expected_counts} == expected_counts

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    report = BookTransferService(BookRepository(target_db)).import_json(payload)
    assert int(report) == 1
    assert dict(report.extras) == expected_counts
    with target_db.connect() as conn:
        for table, count in expected_counts.items():
            actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert actual == count, f"{table}: {actual} != {count}"


def test_reimport_of_related_domains_is_idempotent(tmp_path):
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    repository = BookRepository(source_db)
    book_id = repository.create_book(Book(title="کتاب", authors=("نویسنده",)))
    repository.add_reading_session("session-1", book_id, "2026-09-27", 30, 5, None)
    repository.add_copy("copy-1", book_id)
    repository.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-27", "2026-10-27")
    payload = BookTransferService(repository).export_json()

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookTransferService(BookRepository(target_db))
    first = target.import_json(payload)
    assert first.extra_count == 3

    second = target.import_json(payload)
    assert second.imported == 0
    assert second.updated == 1  # the book itself, by id — merge semantics
    assert second.extras == ()
    assert second.skipped == ()
    with target_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reading_sessions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM physical_copies").fetchone()[0] == 1


def test_schema_version_1_payload_still_imports(tmp_path):
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    repository = BookRepository(source_db)
    repository.create_book(Book(title="کتاب قدیمی", authors=("نویسنده",)))
    data = json.loads(BookTransferService(repository).export_json())

    # Simulate an export made before schema v2: same key set as version 1.
    v1_keys = (
        "books",
        "book_personal",
        "tags",
        "shelves",
        "book_tags",
        "book_shelves",
    )
    v1 = {key: data[key] for key in v1_keys}
    v1["schema_version"] = 1
    v1["exported_at"] = "2026-01-01T00:00:00+00:00"

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    report = BookTransferService(BookRepository(target_db)).import_json(
        json.dumps(v1, ensure_ascii=False)
    )
    assert int(report) == 1
    assert report.extras == ()
    assert BookRepository(target_db).list()[0]["title"] == "کتاب قدیمی"


def test_unknown_json_schema_version_is_rejected(tmp_path):
    db = Database(tmp_path / "target.sqlite3")
    db.migrate()
    with pytest.raises(ValueError, match="unsupported JSON schema version"):
        BookTransferService(BookRepository(db)).import_json(
            json.dumps({"schema_version": 99, "books": []})
        )


def test_csv_with_unknown_column_is_rejected(tmp_path):
    db = Database(tmp_path / "target.sqlite3")
    db.migrate()
    service = BookTransferService(BookRepository(db))
    broken = service.export_csv().replace("title", "book_title", 1)
    with pytest.raises(ValueError, match="unsupported CSV schema"):
        service.import_csv(broken)


def test_related_rows_with_missing_references_are_skipped_visibly(tmp_path):
    payload = json.dumps(
        {
            "schema_version": 2,
            "exported_at": "2026-10-09T00:00:00+00:00",
            "books": [],
            "reading_sessions": [
                {
                    "id": "s1",
                    "book_id": "missing-book",
                    "started_at": "2026-09-27",
                    "minutes": 30,
                    "pages": 5,
                    "note": None,
                }
            ],
        },
        ensure_ascii=False,
    )
    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    report = BookTransferService(BookRepository(target_db)).import_json(payload)
    assert int(report) == 0
    assert report.extra_count == 0
    assert (
        "s1",
        "reading_sessions: book_id missing-book not found",
    ) in report.skipped
    with target_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reading_sessions").fetchone()[0] == 0
