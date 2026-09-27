from dataclasses import dataclass

from books.db import BookRepository, Database
from books.enrichment import MetadataEnricher
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


def test_enrichment_fills_missing_fields_and_uses_cache(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 7
    repository = BookRepository(db)
    source = FakeProvider(
        [
            Book(
                title="کتاب",
                authors=("نویسنده",),
                publisher="ناشر",
                pages=120,
                cover_url="https://example.test/cover.jpg",
                source_ids={"fake": "1"},
            )
        ]
    )
    enricher = MetadataEnricher(repository, [("fake", source)], cache_ttl_seconds=3600)
    current = Book(title="کتاب")

    first = enricher.enrich(current)
    assert first.publisher == "ناشر"
    assert first.pages == 120
    assert source.calls == 1

    second = enricher.enrich(current)
    assert second.cover_url == "https://example.test/cover.jpg"
    assert source.calls == 1

    third = enricher.enrich(current, force_refresh=True)
    assert third.publisher == "ناشر"
    assert source.calls == 2


def test_enrichment_does_not_fail_when_provider_is_down(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    enricher = MetadataEnricher(
        repository,
        [("bad", FakeProvider(error="down"))],
    )
    current = Book(title="کتاب", publisher="شخصی")
    result = enricher.enrich(current)
    assert result.publisher == "شخصی"
