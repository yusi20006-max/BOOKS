from books.app import library_row_summary


def test_library_row_summary_handles_persian_metadata():
    row = {
        "title": "شازده کوچولو",
        "authors_json": '["آنتوان دو سنت اگزوپری"]',
        "publisher": "نشر نمونه",
        "publication_year": 1943,
        "isbn13": "9780156012195",
        "isbn10": None,
    }
    summary = library_row_summary(row)
    assert summary == {
        "title": "شازده کوچولو",
        "authors": "آنتوان دو سنت اگزوپری",
        "publisher": "نشر نمونه",
        "year": "1943",
        "isbn": "9780156012195",
    }


def test_library_row_summary_uses_fallbacks():
    row = {
        "title": "کتاب",
        "authors_json": "[]",
        "publisher": None,
        "publication_year": None,
        "isbn13": None,
        "isbn10": "0140328726",
    }
    summary = library_row_summary(row)
    assert summary["authors"] == "—"
    assert summary["publisher"] == "—"
    assert summary["year"] == "—"
    assert summary["isbn"] == "0140328726"
