import pytest

from books.db import BookRepository, Database
from books.models import Book


def test_library_search_normalizes_persian_characters_and_zwnj(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    repository.create_book(
        Book(
            title="شازده‌کوچولو",
            authors=("آنتوان دو سنت اگزوپری",),
            translators=("محمد قاضی",),
            publisher="نشر نمونه",
            isbn13="9780156012195",
        )
    )

    rows = repository.search("شازده كوچولو")
    assert len(rows) == 1
    assert rows[0]["title"] == "شازده‌کوچولو"

    assert repository.search("محمد قاضی")
    assert len(repository.search("978-0156012195")) == 1


def test_library_search_supports_isbn_without_punctuation(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    repository.create_book(Book(title="کتاب", isbn13="9780156012195"))

    assert len(repository.search("9780156012195")) == 1


def test_library_search_rejects_empty_query(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)

    with pytest.raises(ValueError):
        repository.search("   ")
