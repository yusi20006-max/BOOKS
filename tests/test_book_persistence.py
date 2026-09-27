import sqlite3

import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_create_book_round_trips_and_prevents_duplicate_isbn(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 8
    repository = BookRepository(db)

    book = Book(
        title="شازده کوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        translators=("احمد شاملو",),
        publisher="نشر نمونه",
        pages=96,
        publication_year=1943,
        isbn13="9780156012195",
        language="fa",
    )
    book_id = repository.create_book(book)

    row = repository.get(book_id)
    assert row is not None
    assert row["title"] == "شازده کوچولو"
    assert row["isbn13"] == "9780156012195"
    assert '"احمد شاملو"' in row["translators_json"]

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_book(book)

    assert repository.list() and len(repository.list()) == 1


def test_create_book_uses_transaction_and_can_reload(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)

    book_id = repository.create_book(Book(title="کتاب آفلاین"))
    reopened = BookRepository(Database(tmp_path / "books.sqlite3")).get(book_id)

    assert reopened is not None
    assert reopened["title"] == "کتاب آفلاین"
