from books.db import BookRepository, Database
from books.models import Book


def test_phase16_25_persistence_boundary(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 10
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب یک", authors=("نویسنده",)))

    repository.add_reading_session("session-1", book_id, "2026-09-27", 45, 12, "یادداشت")
    repository.add_note("note-1", book_id, "یادداشت دانشی", 12)
    repository.add_quote("quote-1", book_id, "نقل قول", 14, "صفحه ۱۴")
    repository.add_copy("copy-1", book_id, internal_code="BK-001")
    repository.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-27", "2026-10-01")

    assert repository.list_reading_sessions(book_id)[0]["pages"] == 12
    knowledge = repository.list_knowledge(book_id)
    assert knowledge["notes"][0]["text"] == "یادداشت دانشی"
    assert knowledge["quotes"][0]["text"] == "نقل قول"
    assert repository.list_loans()[0]["copy_id"] == "copy-1"

    reopened = BookRepository(Database(db.path))
    assert reopened.list_reading_sessions(book_id)[0]["minutes"] == 45
