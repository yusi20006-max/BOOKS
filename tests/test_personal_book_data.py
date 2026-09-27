import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_personal_data_is_separate_and_persistent(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 8
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب", publisher="ناشر"))

    repository.update_personal_data(
        book_id,
        rating=5,
        note="یادداشت من",
        quote="نقل‌قول من",
    )

    row = repository.get_personal_data(book_id)
    assert row["rating"] == 5
    assert row["note"] == "یادداشت من"
    assert row["quote"] == "نقل‌قول من"
    assert repository.get(book_id)["publisher"] == "ناشر"


def test_personal_rating_is_validated(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    with pytest.raises(ValueError, match="between 1 and 5"):
        repository.update_personal_data(
            book_id,
            rating=6,
            note="",
            quote="",
        )
