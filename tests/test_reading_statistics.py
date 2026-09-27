from books.db import BookRepository, Database
from books.models import Book


def test_reading_statistics_are_derived_from_library(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    first = repository.create_book(
        Book(title="اول", authors=("نویسنده الف",), pages=100)
    )
    second = repository.create_book(
        Book(title="دوم", authors=("نویسنده الف", "نویسنده ب"), pages=200)
    )
    repository.update_reading_status(first, "reading")
    repository.update_reading_progress(first, 50)
    repository.update_reading_status(second, "finished")
    repository.update_reading_progress(second, 200)

    stats = repository.reading_statistics()
    assert stats["book_count"] == 2
    assert stats["authors_count"] == 2
    assert stats["total_pages"] == 300
    assert stats["current_pages"] == 250
    assert stats["status_counts"]["reading"] == 1
    assert stats["status_counts"]["finished"] == 1
    assert stats["progress_trend"]
