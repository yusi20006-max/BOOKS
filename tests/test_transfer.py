from books.db import BookRepository, Database
from books.models import Book
from books.transfer import BookTransferService


def test_json_round_trip_preserves_core_and_personal_data(tmp_path):
    db = Database(tmp_path / "source.sqlite3")
    assert db.migrate() == 10
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
    assert target.import_json(payload) == 1

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
    assert target.import_csv(payload) == 1
    assert BookRepository(target_db).list()[0]["title"] == "کتاب فارسی"
