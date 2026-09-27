from dataclasses import dataclass

from books.models import Book
from books.persian_providers import PersianProviderRegistry


@dataclass
class FakeProvider:
    name: str
    books: tuple[Book, ...]
    fail: bool = False

    def search(self, query: str, *, limit: int = 10):
        if self.fail:
            raise RuntimeError("source unavailable")
        return self.books[:limit]


def test_registry_keeps_provider_contract_independent_from_ui():
    book = Book(title="کتاب فارسی")
    registry = PersianProviderRegistry((FakeProvider("local", (book,)),))
    assert registry.search("کتاب") == (book,)


def test_registry_isolates_optional_provider_failure():
    book = Book(title="کتاب فارسی")
    registry = PersianProviderRegistry((FakeProvider("broken", (), True), FakeProvider("ok", (book,))))
    assert registry.search("کتاب") == (book,)


def test_registry_rejects_duplicate_provider_names():
    try:
        PersianProviderRegistry((FakeProvider("same", ()), FakeProvider("same", ())))
    except ValueError:
        return
    raise AssertionError("duplicate provider names must be rejected")
