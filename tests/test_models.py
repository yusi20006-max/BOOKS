import pytest

from books.models import Book
from books.normalization import normalize_isbn, normalize_text, validate_isbn10, validate_isbn13


def test_persian_normalization_preserves_display_separately():
    assert normalize_text("  كتاب  ") == "کتاب"
    assert normalize_text("می‌ روم") == "می‌روم"
    assert normalize_text("سال ۱۴۰۲") == "سال 1402"


def test_isbn_normalization_and_validation():
    assert normalize_isbn("978-0-306-40615-7") == "9780306406157"
    assert validate_isbn13("9780306406157")
    assert validate_isbn10("0-306-40615-2")
    assert not validate_isbn13("9780306406158")


def test_book_normalizes_fields_and_rejects_invalid_values():
    book = Book(title=" كتاب نمونه ", authors=("  نویسنده  ",), isbn13="978-0-306-40615-7")
    assert book.title == "کتاب نمونه"
    assert book.authors == ("نویسنده",)
    assert book.isbn13 == "9780306406157"

    with pytest.raises(ValueError, match="title"):
        Book(title="   ")
    with pytest.raises(ValueError, match="ISBN-13"):
        Book(title="کتاب", isbn13="9780306406158")
    with pytest.raises(ValueError, match="pages"):
        Book(title="کتاب", pages=-1)
