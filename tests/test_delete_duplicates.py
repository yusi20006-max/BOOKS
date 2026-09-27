from books.db import BookRepository, Database
from books.models import Book


def test_find_duplicates_matches_isbn_and_normalized_title_author(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)

    existing_id = repository.create_book(
        Book(
            title="شازده‌کوچولو",
            authors=("آنتوان دو سنت اگزوپری",),
            isbn13="9780156012195",
        )
    )

    duplicate = Book(
        title="شازده كوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        isbn13="9780156012195",
    )
    matches = repository.find_duplicates(duplicate)
    assert [row["id"] for row in matches] == [existing_id]

    assert repository.find_duplicates(duplicate, exclude_id=existing_id) == []


def test_delete_is_explicit_and_removes_only_selected_record(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    first = repository.create_book(Book(title="اول"))
    second = repository.create_book(Book(title="دوم"))

    assert repository.delete(first) is True
    assert repository.get(first) is None
    assert repository.get(second) is not None
    assert repository.delete(first) is False
