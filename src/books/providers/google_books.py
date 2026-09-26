from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..models import Book
from ..normalization import normalize_isbn, validate_isbn10, validate_isbn13


class GoogleBooksError(RuntimeError):
    """Raised when Google Books cannot provide a valid response."""


@dataclass(frozen=True, slots=True)
class GoogleBooksPage:
    items: tuple[Book, ...]
    total_items: int
    start_index: int
    max_results: int


class GoogleBooksProvider:
    BASE_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._client = client

    def search(
        self,
        query: str,
        *,
        language: str = "fa",
        start_index: int = 0,
        max_results: int = 20,
    ) -> GoogleBooksPage:
        if not query.strip():
            raise ValueError("query must not be empty")
        if start_index < 0:
            raise ValueError("start_index must be non-negative")
        if not 1 <= max_results <= 40:
            raise ValueError("max_results must be between 1 and 40")

        params: dict[str, Any] = {
            "q": query.strip(),
            "langRestrict": language,
            "startIndex": start_index,
            "maxResults": max_results,
            "projection": "full",
        }
        if self.settings.google_books_api_key:
            params["key"] = self.settings.google_books_api_key

        headers = {"User-Agent": self.settings.user_agent}
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        )
        try:
            response = client.get(self.BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GoogleBooksError("Google Books request failed") from exc
        finally:
            if owns_client:
                client.close()

        items = tuple(
            book
            for raw in payload.get("items", [])
            if (book := _map_volume(raw)) is not None
        )
        return GoogleBooksPage(
            items=items,
            total_items=int(payload.get("totalItems", 0)),
            start_index=start_index,
            max_results=max_results,
        )


def _map_volume(raw: dict[str, Any]) -> Book | None:
    info = raw.get("volumeInfo") or {}
    title = info.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    isbn10 = isbn13 = None
    for identifier in info.get("industryIdentifiers") or []:
        kind = identifier.get("type")
        value = normalize_isbn(identifier.get("identifier"))
        if kind == "ISBN_10" and value and validate_isbn10(value):
            isbn10 = value
        elif kind == "ISBN_13" and value and validate_isbn13(value):
            isbn13 = value

    year = _publication_year(info.get("publishedDate"))
    image_links = info.get("imageLinks") or {}
    cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")

    return Book(
        title=title,
        authors=tuple(info.get("authors") or ()),
        publisher=info.get("publisher"),
        pages=info.get("pageCount"),
        publication_year=year,
        isbn10=isbn10,
        isbn13=isbn13,
        language=info.get("language"),
        genres=tuple(info.get("categories") or ()),
        summary=info.get("description"),
        cover_url=cover_url,
        source_ids={"google_books": str(raw.get("id", ""))},
    )


def _publication_year(value: Any) -> int | None:
    if not isinstance(value, str) or len(value) < 4:
        return None
    try:
        year = int(value[:4])
    except ValueError:
        return None
    return year if 1 <= year <= 9999 else None
