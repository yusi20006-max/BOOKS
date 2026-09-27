import sqlite3
import time

import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_update_book_changes_record_without_creating_duplicate(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(
        Book(title="کتاب قدیمی", isbn13="9780156012195", authors=("نویسنده",))
    )
    before = repository.get(book_id)["updated_at"]

    time.sleep(0.001)
    updated = Book(
        title="کتاب ویرایش‌شده",
        isbn13="9780156012195",
        authors=("نویسنده", "نویسنده دوم"),
    )
    assert repository.update_book(book_id, updated) is True

    row = repository.get(book_id)
    assert row["title"] == "کتاب ویرایش‌شده"
    assert row["authors_json"] != '["نویسنده"]'
    assert row["updated_at"] != before
    assert len(repository.list()) == 1


def test_update_book_rejects_duplicate_isbn_without_mutating_target(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    first = repository.create_book(Book(title="اول", isbn13="9780156012195"))
    second = repository.create_book(Book(title="دوم", isbn13="9780306406157"))

    with pytest.raises(sqlite3.IntegrityError):
        repository.update_book(
            second,
            Book(title="دوم تغییر یافته", isbn13="9780156012195"),
        )

    assert repository.get(second)["title"] == "دوم"
    assert repository.get(first)["title"] == "اول"
