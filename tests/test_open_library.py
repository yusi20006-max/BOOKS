import httpx
import pytest

from books.config import Settings
from books.providers.open_library import OpenLibraryError, OpenLibraryProvider


def settings():
    return Settings(
        db_path="data/books.sqlite3",
        host="127.0.0.1",
        port=8501,
        request_timeout_seconds=3.0,
        user_agent="BOOKS/test",
        google_books_api_key=None,
        open_library_base_url="https://openlibrary.org",
    )


def test_search_maps_open_library_result():
    payload = {
        "numFound": 1,
        "docs": [{
            "key": "/works/OL123W",
            "title": "کتاب نمونه",
            "author_name": ["نویسنده"],
            "first_publish_year": 1400,
            "publisher": ["ناشر"],
            "number_of_pages_median": 120,
            "isbn": ["9780306406157"],
            "language": ["per"],
            "cover_i": 12345,
            "subject": ["ادبیات"],
        }],
    }

    def handler(request):
        assert request.url.path.endswith("/search.json")
        assert request.url.params["lang"] == "fa"
        assert request.url.params["limit"] == "10"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = OpenLibraryProvider(settings(), client).search("کتاب", limit=10)

    assert result.total_items == 1
    assert result.items[0].title == "کتاب نمونه"
    assert result.items[0].isbn13 == "9780306406157"
    assert result.items[0].source_ids["open_library"] == "works/OL123W"


def test_isbn_lookup_maps_edition():
    payload = {
        "key": "/books/OL123M",
        "title": "کتاب نمونه",
        "authors": [{"name": "نویسنده"}],
        "publishers": ["ناشر"],
        "publish_date": "2020",
        "number_of_pages": 200,
        "isbn_13": ["9780306406157"],
        "languages": [{"key": "/languages/per"}],
        "covers": [123],
    }

    def handler(request):
        assert request.url.path.endswith("/isbn/9780306406157.json")
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = OpenLibraryProvider(settings(), client).isbn_lookup("978-0-306-40615-7")

    assert result.isbn13 == "9780306406157"
    assert result.language == "per"
    assert result.pages == 200


def test_open_library_failure_is_wrapped():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(OpenLibraryError):
        OpenLibraryProvider(settings(), client).search("کتاب")
