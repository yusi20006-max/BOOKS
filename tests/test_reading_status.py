import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_reading_status_defaults_to_unread_and_persists(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 2
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    assert repository.get(book_id)["reading_status"] == "unread"
    assert repository.update_reading_status(book_id, "reading") is True
    assert repository.get(book_id)["reading_status"] == "reading"

    reopened = BookRepository(Database(tmp_path / "books.sqlite3"))
    reopened.db.migrate()
    assert reopened.get(book_id)["reading_status"] == "reading"


def test_reading_status_rejects_unknown_value(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    with pytest.raises(ValueError):
        repository.update_reading_status(book_id, "paused")
