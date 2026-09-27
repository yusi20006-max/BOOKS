from books.db import BookRepository, Database
from books.models import Book


def test_favorite_and_many_to_many_tags_shelves_persist(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 8
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title="کتاب"))

    repository.update_favorite(book_id, True)
    repository.set_organization(
        book_id,
        tags=(" فارسی ", "دانش", "فارسی"),
        shelves=("مطالعه", "مرجع"),
    )

    personal = repository.get_personal_data(book_id)
    assert personal["favorite"] == 1
    tags, shelves = repository.get_organization(book_id)
    assert tags == ("دانش", "فارسی")
    assert shelves == ("مرجع", "مطالعه")


def test_organization_requires_existing_book(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)

    try:
        repository.set_organization("missing", tags=("کتاب",), shelves=())
    except ValueError as exc:
        assert "book not found" in str(exc)
    else:
        raise AssertionError("missing book must fail")
