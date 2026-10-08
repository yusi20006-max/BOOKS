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
