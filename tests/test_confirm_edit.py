from books.app import build_edited_book


def test_build_edited_book_normalizes_and_validates_metadata():
    book = build_edited_book(
        title="  شازده کوچولو ",
        original_title="Le Petit Prince",
        authors="آنتوان دو سنت اگزوپری\n",
        translators="احمد شاملو\nمحمد قاضی",
        publisher="نشر نمونه",
        pages=96,
        publication_year=1943,
        isbn10="0-15-601219-7",
        isbn13="978-015601219-5",
        language="fa",
        genres="داستان\nکودک",
        subjects="ادبیات",
        summary="خلاصه",
        cover_url="https://example.test/cover.jpg",
        source_ids={"google_books": "g-1"},
    )
    assert book.title == "شازده کوچولو"
    assert book.translators == ("احمد شاملو", "محمد قاضی")
    assert book.pages == 96
    assert book.isbn10 == "0156012197"
    assert book.isbn13 == "9780156012195"


def test_build_edited_book_rejects_invalid_isbn():
    try:
        build_edited_book(
            title="کتاب",
            original_title="",
            authors="نویسنده",
            translators="",
            publisher="",
            pages=1,
            publication_year=1400,
            isbn10="123",
            isbn13="",
            language="fa",
            genres="",
            subjects="",
            summary="",
            cover_url="",
            source_ids={},
        )
    except ValueError as exc:
        assert "ISBN-10" in str(exc)
    else:
        raise AssertionError("invalid ISBN must be rejected")
