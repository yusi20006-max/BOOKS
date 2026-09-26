import httpx

from books.config import Settings
from books.providers.google_books import GoogleBooksError, GoogleBooksProvider


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


def test_google_books_maps_persian_result():
    payload = {
        "totalItems": 1,
        "items": [{
            "id": "abc123",
            "volumeInfo": {
                "title": "كتاب نمونه",
                "authors": ["نویسنده"],
                "publisher": "ناشر",
                "publishedDate": "2024-05-01",
                "pageCount": 120,
                "language": "fa",
                "industryIdentifiers": [
                    {"type": "ISBN_13", "identifier": "9780306406157"}
                ],
                "categories": ["Literature"],
                "description": "توضیح",
                "imageLinks": {"thumbnail": "https://example.test/cover.jpg"},
            },
        }],
    }

    def handler(request):
        assert request.url.params["q"] == "شازده کوچولو"
        assert request.url.params["langRestrict"] == "fa"
        assert request.url.params["maxResults"] == "10"
        assert request.headers["User-Agent"] == "BOOKS/test"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = GoogleBooksProvider(settings(), client).search("شازده کوچولو", max_results=10)

    assert result.total_items == 1
    assert result.items[0].title == "کتاب نمونه"
    assert result.items[0].isbn13 == "9780306406157"
    assert result.items[0].source_ids["google_books"] == "abc123"


def test_google_books_rejects_invalid_query():
    provider = GoogleBooksProvider(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))))
    try:
        provider.search(" ")
    except ValueError as exc:
        assert "query" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_google_books_translates_http_failures():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    try:
        GoogleBooksProvider(settings(), client).search("کتاب")
    except GoogleBooksError:
        pass
    else:
        raise AssertionError("expected GoogleBooksError")
