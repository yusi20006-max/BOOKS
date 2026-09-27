from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from .db import BookRepository
from .discovery import DiscoveryResponse, DiscoveryResult, DiscoveryService
from .models import Book
from .normalization import normalize_isbn, normalize_text


class MetadataEnricher:
    """Fill missing Book metadata from providers without touching personal data."""

    def __init__(
        self,
        repository: BookRepository,
        providers: Sequence[tuple[str, Any]],
        *,
        cache_ttl_seconds: int = 86_400,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        if cache_ttl_seconds < 0:
            raise ValueError("cache TTL must be non-negative")
        self.repository = repository
        self.providers = tuple(providers)
        self.cache_ttl_seconds = cache_ttl_seconds

    def enrich(
        self,
        book: Book,
        *,
        language: str = "fa",
        force_refresh: bool = False,
    ) -> Book:
        results: list[DiscoveryResult] = []
        for name, provider in self.providers:
            try:
                payload = None
                if not force_refresh:
                    payload = self.repository.get_metadata_cache(
                        name,
                        self._cache_key(book),
                        language,
                        self.cache_ttl_seconds,
                    )
                if payload is not None:
                    items = tuple(self._books_from_json(payload))
                else:
                    page = provider.search(
                        book.title,
                        language=language,
                        start_index=0,
                        limit=5,
                    )
                    items = tuple(item for item in page.items if isinstance(item, Book))
                    self.repository.set_metadata_cache(
                        name,
                        self._cache_key(book),
                        language,
                        json.dumps(
                            [self._book_to_dict(item) for item in items],
                            ensure_ascii=False,
                        ),
                    )
                results.append(DiscoveryResult(name, items, len(items)))
            except Exception as exc:  # noqa: BLE001
                results.append(DiscoveryResult(name, (), 0, str(exc)))

        merged = DiscoveryService.merge_results(
            DiscoveryResponse(tuple(results), ())
        )
        candidate = self._select_candidate(book, merged)
        return self._fill_missing(book, candidate.book if candidate else None)

    @staticmethod
    def _cache_key(book: Book) -> str:
        isbn = normalize_isbn(book.isbn13 or book.isbn10 or "")
        return isbn or normalize_text(book.title).casefold()

    @staticmethod
    def _select_candidate(book: Book, candidates: Sequence[Any]) -> Any | None:
        if not candidates:
            return None
        wanted_isbn = {
            value
            for value in (normalize_isbn(book.isbn10), normalize_isbn(book.isbn13))
            if value
        }
        if wanted_isbn:
            for candidate in candidates:
                candidate_isbn = {
                    value
                    for value in (
                        normalize_isbn(candidate.book.isbn10),
                        normalize_isbn(candidate.book.isbn13),
                    )
                    if value
                }
                if wanted_isbn & candidate_isbn:
                    return candidate

        title = normalize_text(book.title)
        authors = {normalize_text(author).casefold() for author in book.authors}
        for candidate in candidates:
            if normalize_text(candidate.book.title) == title:
                candidate_authors = {
                    normalize_text(author).casefold()
                    for author in candidate.book.authors
                }
                if not authors or authors & candidate_authors:
                    return candidate
        return candidates[0]

    @staticmethod
    def _fill_missing(current: Book, source: Book | None) -> Book:
        if source is None:
            return current
        return replace(
            current,
            original_title=current.original_title or source.original_title,
            authors=current.authors or source.authors,
            translators=current.translators or source.translators,
            publisher=current.publisher or source.publisher,
            pages=current.pages if current.pages is not None else source.pages,
            publication_year=(
                current.publication_year
                if current.publication_year is not None
                else source.publication_year
            ),
            isbn10=current.isbn10 or source.isbn10,
            isbn13=current.isbn13 or source.isbn13,
            language=current.language or source.language,
            genres=current.genres or source.genres,
            subjects=current.subjects or source.subjects,
            summary=current.summary or source.summary,
            cover_url=current.cover_url or source.cover_url,
            source_ids={**source.source_ids, **current.source_ids},
            notes=current.notes,
        )

    @staticmethod
    def _book_to_dict(book: Book) -> dict[str, Any]:
        return {
            "title": book.title,
            "original_title": book.original_title,
            "authors": list(book.authors),
            "translators": list(book.translators),
            "publisher": book.publisher,
            "pages": book.pages,
            "publication_year": book.publication_year,
            "isbn10": book.isbn10,
            "isbn13": book.isbn13,
            "language": book.language,
            "genres": list(book.genres),
            "subjects": list(book.subjects),
            "summary": book.summary,
            "cover_url": book.cover_url,
            "source_ids": dict(book.source_ids),
            "notes": book.notes,
        }

    @staticmethod
    def _books_from_json(payload: str) -> list[Book]:
        return [Book(**item) for item in json.loads(payload)]
