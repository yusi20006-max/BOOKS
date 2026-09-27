from dataclasses import dataclass

from books.discovery import DiscoveryService
from books.models import Book


@dataclass
class Page:
    items: tuple
    total_items: int


class FakeProvider:
    def __init__(self, items=(), error=None):
        self.items = tuple(items)
        self.error = error
        self.calls = 0

    def search(self, query, *, language, start_index, limit):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return Page(self.items, len(self.items))


def test_parallel_strategy_is_provider_agnostic():
    google = FakeProvider(("g",))
    open_library = FakeProvider(("o",))
    response = DiscoveryService(
        [("google", google), ("open_library", open_library)]
    ).search("کتاب")

    assert [r.provider for r in response.results] == ["google", "open_library"]
    assert response.results[0].items == ("g",)
    assert response.failures == ()


def test_sequential_strategy_falls_back_after_failure():
    failing = FakeProvider(error="temporary failure")
    working = FakeProvider(("ok",))
    response = DiscoveryService(
        [("first", failing), ("second", working)]
    ).search("کتاب", strategy="sequential")

    assert response.results[0].error == "temporary failure"
    assert response.results[1].items == ("ok",)
    assert [f.provider for f in response.failures] == ["first"]


def test_parallel_failure_does_not_hide_success():
    response = DiscoveryService(
        [("bad", FakeProvider(error="down")), ("good", FakeProvider(("ok",)))]
    ).search("کتاب", strategy="parallel")

    assert len(response.failures) == 1
    assert response.results[1].items == ("ok",)


def test_merge_results_deduplicates_shared_isbn_and_keeps_provenance():
    google_book = Book(
        title="شازده کوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        isbn13="9780156012195",
        source_ids={"google_books": "g-1"},
    )
    open_library_book = Book(
        title="شازده کوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        isbn13="9780156012195",
        publisher="Publisher",
        cover_url="https://example.test/cover.jpg",
        source_ids={"open_library": "ol-1"},
    )

    response = DiscoveryResponse(
        results=(
            DiscoveryResult("google_books", (google_book,), 1),
            DiscoveryResult("open_library", (open_library_book,), 1),
        ),
        failures=(),
    )

    merged = DiscoveryService.merge_results(response)

    assert len(merged) == 1
    assert merged[0].confidence == 1.0
    assert merged[0].matched_by == ("isbn",)
    assert [(p.provider, p.source_id) for p in merged[0].provenance] == [
        ("google_books", "g-1"),
        ("open_library", "ol-1"),
    ]
    assert merged[0].book.publisher == "Publisher"
    assert merged[0].book.cover_url == "https://example.test/cover.jpg"


def test_merge_results_matches_normalized_title_and_author_without_isbn():
    first = Book(title="  شازده‌ کوچولو ", authors=("آنتوان دو سنت اگزوپری",))
    second = Book(title="شازده  کوچولو", authors=("آنتوان دو سنت اگزوپری",), pages=96)

    response = DiscoveryResponse(
        results=(
            DiscoveryResult("first", (first,), 1),
            DiscoveryResult("second", (second,), 1),
        ),
        failures=(),
    )

    merged = DiscoveryService.merge_results(response)

    assert len(merged) == 2
    assert merged[0].matched_by == ("title", "author")
    assert merged[0].book.pages == 96


def test_merge_results_does_not_collapse_different_translations_without_isbn():
    first = Book(
        title="شازده کوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        translators=("احمد شاملو",),
    )
    second = Book(
        title="شازده کوچولو",
        authors=("آنتوان دو سنت اگزوپری",),
        translators=("محمد قاضی",),
    )

    response = DiscoveryResponse(
        results=(
            DiscoveryResult("google_books", (first,), 1),
            DiscoveryResult("open_library", (second,), 1),
        ),
        failures=(),
    )

    merged = DiscoveryService.merge_results(response)

    assert len(merged) == 1
    assert merged[0].confidence == 0.95


def test_search_merged_exposes_normalized_candidates():
    first = Book(title="کتاب نمونه", authors=("نویسنده",), source_ids={"a": "1"})
    second = Book(title="کتاب نمونه", authors=("نویسنده",), source_ids={"b": "2"})

    service = DiscoveryService(
        [("a", FakeProvider((first,))), ("b", FakeProvider((second,)))]
    )

    merged = service.search_merged("کتاب نمونه")

    assert len(merged) == 1
    assert {item.provider for item in merged[0].provenance} == {"a", "b"}
