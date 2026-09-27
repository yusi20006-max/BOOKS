from books.db import BookRepository, Database
from books.models import Book


def test_filter_books_combines_persian_filters_and_sorting(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)

    repository.create_book(
        Book(
            title="کتاب اول",
            authors=("نویسنده الف",),
            publisher="ناشر الف",
            publication_year=1402,
            language="fa",
            genres=("داستان",),
        )
    )
    repository.create_book(
        Book(
            title="کتاب دوم",
            authors=("نویسنده الف",),
            publisher="ناشر ب",
            publication_year=1403,
            language="fa",
            genres=("علمی",),
        )
    )

    rows = repository.filter_books(
        author="نویسنده الف",
        publisher="ناشر الف",
        language="fa",
        sort_by="publication_year",
        descending=False,
    )
    assert len(rows) == 1
    assert rows[0]["title"] == "کتاب اول"

    rows = repository.filter_books(genre="علمی", publication_year=1403)
    assert len(rows) == 1
    assert rows[0]["title"] == "کتاب دوم"


def test_filter_books_rejects_invalid_sort(tmp_path):
    repository = BookRepository(Database(tmp_path / "books.sqlite3"))
    repository.db.migrate()

    try:
        repository.filter_books(sort_by="rating")
    except ValueError as exc:
        assert "unsupported sort field" in str(exc)
    else:
        raise AssertionError("invalid sort field must fail")
