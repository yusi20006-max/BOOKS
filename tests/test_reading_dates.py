import datetime as dt

import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_reading_dates_are_timezone_safe_and_persistent(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 11
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    started = repository.start_reading(book_id)
    started_value = dt.datetime.fromisoformat(started)
    assert started_value.tzinfo is not None
    assert repository.get(book_id)["reading_started_at"] == started

    finished = repository.finish_reading(book_id)
    finished_value = dt.datetime.fromisoformat(finished)
    assert finished_value.tzinfo is not None
    assert repository.get(book_id)["reading_finished_at"] == finished


def test_reading_cannot_finish_before_start(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    with pytest.raises(ValueError, match="started"):
        repository.finish_reading(book_id)


def test_start_reading_twice_keeps_first_timestamp(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    first = repository.start_reading(book_id)
    stored = repository.get(book_id)["reading_started_at"]
    assert stored == first

    with pytest.raises(ValueError) as excinfo:
        repository.start_reading(book_id)
    assert "قبلاً شروع شده" in str(excinfo.value)
    assert repository.get(book_id)["reading_started_at"] == stored
    assert repository.finish_reading(book_id)  # guard does not break finish


def test_start_reading_unknown_book_still_raises(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    with pytest.raises(ValueError, match="book not found"):
        repository.start_reading("missing")
