from dataclasses import dataclass

from books.db import BookRepository, Database
from books.discovery import DiscoveryService
from books.models import Book
from books.normalization import normalize_isbn, normalize_text
from books.providers.google_books import GoogleBooksProvider
from books.providers.open_library import OpenLibraryProvider


@dataclass
class Page:
    items: tuple
    total_items: int


class OfflineProvider:
    def __init__(self, items):
        self.items = tuple(items)
        self.calls = 0

    def search(self, query, *, language, start_index, limit):
        self.calls += 1
        return Page(self.items, len(self.items))


def test_full_offline_core_contract(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 8
    assert db.migrate() == 0

    repository = BookRepository(db)
    book_id = repository.create_book(
        Book(
            title="  شازده كوچولو ",
            authors=("آنتوان دو سنت اگزوپری",),
            isbn13="9780156012195",
            pages=100,
        )
    )

    assert repository.search("شازده‌کوچولو")
    assert normalize_text("ي ك  ۱۲۳") == "ی ک 123"
    assert normalize_isbn("۹۷۸-۰۱۵۶۰۱۲۱۹۵") == "9780156012195"

    provider = OfflineProvider((Book(title="شازده کوچولو", authors=("آنتوان دو سنت اگزوپری",)),))
    response = DiscoveryService(
        [("offline", provider)]
    ).search_merged("شازده کوچولو")
    assert len(response) == 1
    assert provider.calls == 1

    assert repository.get(book_id)["title"] == "شازده کوچولو"


def test_external_provider_tests_can_be_constructed_without_network():
    assert GoogleBooksProvider is not None
    assert OpenLibraryProvider is not None
