import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_reading_progress_is_calculated_from_current_page(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 10
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب", pages=200))

    assert repository.update_reading_progress(book_id, 50) == 25
    row = repository.get(book_id)
    assert row["reading_current_page"] == 50
    assert row["reading_progress"] == 25

    assert repository.update_reading_progress(book_id, 200) == 100


def test_reading_progress_validates_total_and_current_page(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    no_pages = repository.create_book(Book(title="بدون صفحات"))
    with pytest.raises(ValueError, match="total pages"):
        repository.update_reading_progress(no_pages, 1)

    book_id = repository.create_book(Book(title="کتاب", pages=100))
    with pytest.raises(ValueError, match="cannot exceed"):
        repository.update_reading_progress(book_id, 101)
