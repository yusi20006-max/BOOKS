from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from .normalization import normalize_isbn, normalize_text, validate_isbn10, validate_isbn13


@dataclass(frozen=True, slots=True)
class Book:
    """Domain representation of a bibliographic work as currently scoped by #3."""

    title: str
    original_title: str | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    translators: tuple[str, ...] = field(default_factory=tuple)
    publisher: str | None = None
    pages: int | None = None
    publication_year: int | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    language: str | None = None
    genres: tuple[str, ...] = field(default_factory=tuple)
    subjects: tuple[str, ...] = field(default_factory=tuple)
    summary: str | None = None
    cover_url: str | None = None
    source_ids: Mapping[str, str] = field(default_factory=dict)
    notes: str | None = None

    def __post_init__(self) -> None:
        title = normalize_text(self.title)
        if not title:
            raise ValueError("title is required")
        if self.pages is not None and self.pages < 0:
            raise ValueError("pages must be non-negative")
        if self.publication_year is not None and not 0 < self.publication_year <= 9999:
            raise ValueError("publication_year must be between 1 and 9999")

        isbn10 = normalize_isbn(self.isbn10)
        isbn13 = normalize_isbn(self.isbn13)
        if isbn10 is not None and not validate_isbn10(isbn10):
            raise ValueError("invalid ISBN-10")
        if isbn13 is not None and not validate_isbn13(isbn13):
            raise ValueError("invalid ISBN-13")

        object.__setattr__(self, "title", title)
        object.__setattr__(self, "original_title", normalize_text(self.original_title) or None)
        object.__setattr__(self, "authors", _clean_people(self.authors))
        object.__setattr__(self, "translators", _clean_people(self.translators))
        object.__setattr__(self, "publisher", normalize_text(self.publisher) or None)
        object.__setattr__(self, "language", normalize_text(self.language) or None)
        object.__setattr__(self, "genres", _clean_values(self.genres))
        object.__setattr__(self, "subjects", _clean_values(self.subjects))
        object.__setattr__(self, "summary", normalize_text(self.summary) or None)
        object.__setattr__(self, "notes", self.notes)
        object.__setattr__(self, "isbn10", isbn10)
        object.__setattr__(self, "isbn13", isbn13)
        object.__setattr__(self, "source_ids", dict(self.source_ids))

    @property
    def search_title(self) -> str:
        return normalize_text(self.title)


def _clean_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(value for value in (normalize_text(v) for v in values) if value)


def _clean_people(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return _clean_values(values)
