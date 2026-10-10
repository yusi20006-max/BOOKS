from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from typing import Any, Protocol

from .models import Book
from .normalization import normalize_isbn, normalize_text


class Provider(Protocol):
    def search(
        self,
        query: str,
        *,
        language: str,
        start_index: int,
        limit: int,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider: str
    message: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    provider: str
    items: tuple[Any, ...]
    total_items: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryResponse:
    results: tuple[DiscoveryResult, ...]
    failures: tuple[ProviderFailure, ...]


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    provider: str
    source_id: str | None


@dataclass(frozen=True, slots=True)
class MergedDiscoveryItem:
    book: Book
    confidence: float
    matched_by: tuple[str, ...]
    provenance: tuple[SourceProvenance, ...]


class DiscoveryService:
    """Provider-agnostic discovery orchestration and deterministic result merging."""

    def __init__(self, providers: Sequence[tuple[str, Provider]]) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        names = [name for name, _ in providers]
        if any(not name.strip() for name in names) or len(names) != len(set(names)):
            raise ValueError("provider names must be non-empty and unique")
        self.providers = tuple(providers)

    def search(
        self,
        query: str,
        *,
        language: str = "fa",
        start_index: int = 0,
        limit: int = 20,
        strategy: str = "parallel",
    ) -> DiscoveryResponse:
        if not query.strip():
            raise ValueError("query must not be empty")
        if strategy not in {"parallel", "sequential"}:
            raise ValueError("strategy must be parallel or sequential")

        if strategy == "sequential":
            return self._search_sequential(query, language, start_index, limit)
        return self._search_parallel(query, language, start_index, limit)

    @staticmethod
    def merge_results(response: DiscoveryResponse) -> tuple[MergedDiscoveryItem, ...]:
        """Merge duplicate Book candidates while retaining provenance.

        Matching is intentionally conservative:
        * shared ISBN is a definitive match;
        * normalized title + at least one normalized author is a strong match;
        * identical normalized titles are merged only when both records have no authors.

        A translated edition with the same title but a different translator is therefore
        not collapsed merely because its title happens to match.
        """

        merged: list[MergedDiscoveryItem] = []
        for result in response.results:
            if result.error:
                continue
            for item in result.items:
                if not isinstance(item, Book):
                    continue

                match_index = None
                match_confidence = 0.0
                match_keys: tuple[str, ...] = ()
                for index, existing in enumerate(merged):
                    confidence, keys = _match_confidence(existing.book, item)
                    if confidence > match_confidence:
                        match_index = index
                        match_confidence = confidence
                        match_keys = keys

                provenance = _provenance(result.provider, item.source_ids)
                if match_index is None:
                    merged.append(
                        MergedDiscoveryItem(
                            book=item,
                            confidence=match_confidence,
                            matched_by=match_keys,
                            provenance=provenance,
                        )
                    )
                    continue

                existing = merged[match_index]
                merged[match_index] = MergedDiscoveryItem(
                    book=_merge_books(existing.book, item),
                    confidence=max(existing.confidence, match_confidence),
                    matched_by=_merge_unique(existing.matched_by, match_keys),
                    provenance=_merge_provenance(existing.provenance, provenance),
                )

        return tuple(merged)

    def search_merged(
        self,
        query: str,
        *,
        language: str = "fa",
        start_index: int = 0,
        limit: int = 20,
        strategy: str = "parallel",
    ) -> tuple[MergedDiscoveryItem, ...]:
        merged, _failures = self.search_merged_detailed(
            query,
            language=language,
            start_index=start_index,
            limit=limit,
            strategy=strategy,
        )
        return merged

    def search_merged_detailed(
        self,
        query: str,
        *,
        language: str = "fa",
        start_index: int = 0,
        limit: int = 20,
        strategy: str = "parallel",
    ) -> tuple[tuple[MergedDiscoveryItem, ...], tuple[ProviderFailure, ...]]:
        """Merge results and expose provider failures alongside them.

        ``search_merged`` keeps its original contract; callers that need to
        distinguish "no connectivity" from "no matches" use this accessor.
        """
        response = self.search(
            query,
            language=language,
            start_index=start_index,
            limit=limit,
            strategy=strategy,
        )
        return self.merge_results(response), response.failures

    def _call(
        self,
        name: str,
        provider: Provider,
        query: str,
        language: str,
        start_index: int,
        limit: int,
    ) -> DiscoveryResult:
        try:
            page = provider.search(
                query,
                language=language,
                start_index=start_index,
                limit=limit,
            )
            return DiscoveryResult(
                provider=name,
                items=tuple(page.items),
                total_items=int(page.total_items),
            )
        except Exception as exc:  # noqa: BLE001
            return DiscoveryResult(
                provider=name,
                items=(),
                total_items=0,
                error=str(exc) or exc.__class__.__name__,
            )

    def _search_sequential(self, query: str, language: str, start_index: int, limit: int) -> DiscoveryResponse:
        results: list[DiscoveryResult] = []
        failures: list[ProviderFailure] = []
        for name, provider in self.providers:
            result = self._call(name, provider, query, language, start_index, limit)
            results.append(result)
            if result.error:
                failures.append(ProviderFailure(name, result.error))
                continue
            break
        return DiscoveryResponse(tuple(results), tuple(failures))

    def _search_parallel(self, query: str, language: str, start_index: int, limit: int) -> DiscoveryResponse:
        results: list[DiscoveryResult] = []
        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            futures = {
                executor.submit(
                    self._call,
                    name,
                    provider,
                    query,
                    language,
                    start_index,
                    limit,
                ): name
                for name, provider in self.providers
            }
            for future in as_completed(futures):
                results.append(future.result())

        order = {name: index for index, (name, _) in enumerate(self.providers)}
        results.sort(key=lambda result: order[result.provider])
        failures = tuple(
            ProviderFailure(result.provider, result.error)
            for result in results
            if result.error
        )
        return DiscoveryResponse(tuple(results), failures)


def _match_confidence(left: Book, right: Book) -> tuple[float, tuple[str, ...]]:
    left_isbns = {value for value in (normalize_isbn(left.isbn10), normalize_isbn(left.isbn13)) if value}
    right_isbns = {value for value in (normalize_isbn(right.isbn10), normalize_isbn(right.isbn13)) if value}
    if left_isbns & right_isbns:
        return 1.0, ("isbn",)

    left_title = _title_match_key(left.title)
    right_title = _title_match_key(right.title)
    if left_title != right_title:
        return 0.0, ()

    left_translators = {_person_key(value) for value in left.translators if _person_key(value)}
    right_translators = {_person_key(value) for value in right.translators if _person_key(value)}
    if left_translators and right_translators and not left_translators & right_translators:
        return 0.0, ()

    left_authors = {_person_key(value) for value in left.authors if _person_key(value)}
    right_authors = {_person_key(value) for value in right.authors if _person_key(value)}
    if left_authors and right_authors and left_authors & right_authors:
        return 0.95, ("title", "author")
    if not left_authors and not right_authors:
        return 0.80, ("title",)
    return 0.0, ()


def _merge_books(primary: Book, secondary: Book) -> Book:
    source_ids = dict(primary.source_ids)
    for provider, source_id in secondary.source_ids.items():
        source_ids.setdefault(provider, source_id)

    return replace(
        primary,
        original_title=primary.original_title or secondary.original_title,
        authors=_merge_values(primary.authors, secondary.authors),
        translators=_merge_values(primary.translators, secondary.translators),
        publisher=primary.publisher or secondary.publisher,
        pages=primary.pages if primary.pages is not None else secondary.pages,
        publication_year=(
            primary.publication_year
            if primary.publication_year is not None
            else secondary.publication_year
        ),
        isbn10=primary.isbn10 or secondary.isbn10,
        isbn13=primary.isbn13 or secondary.isbn13,
        language=primary.language or secondary.language,
        genres=_merge_values(primary.genres, secondary.genres),
        subjects=_merge_values(primary.subjects, secondary.subjects),
        summary=primary.summary or secondary.summary,
        cover_url=primary.cover_url or secondary.cover_url,
        source_ids=source_ids,
    )


def _merge_values(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for value in (*left, *right):
        cleaned = normalize_text(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            values.append(cleaned)
    return tuple(values)


def _merge_unique(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    return _merge_values(left, right)


def _provenance(provider: str, source_ids: Mapping[str, str]) -> tuple[SourceProvenance, ...]:
    source_id = source_ids.get(provider)
    return (SourceProvenance(provider=provider, source_id=source_id),)


def _merge_provenance(
    left: Sequence[SourceProvenance],
    right: Sequence[SourceProvenance],
) -> tuple[SourceProvenance, ...]:
    result = list(left)
    seen = {(item.provider, item.source_id) for item in result}
    for item in right:
        key = (item.provider, item.source_id)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)


def _title_match_key(value: str) -> str:
    return " ".join(normalize_text(value).replace("\u200c", " ").split()).casefold()


def _person_key(value: str) -> str:
    return normalize_text(value).casefold()
