from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..models import Book
from ..normalization import normalize_isbn, validate_isbn10, validate_isbn13


class OpenLibraryError(RuntimeError):
    """Raised when Open Library cannot provide a valid response."""


@dataclass(frozen=True, slots=True)
class OpenLibraryPage:
    items: tuple[Book, ...]
    total_items: int
    start_index: int
    limit: int


class OpenLibraryProvider:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client

    def search(
        self,
        query: str,
        *,
        language: str = "fa",
        start_index: int = 0,
        limit: int = 20,
    ) -> OpenLibraryPage:
        if not query.strip():
            raise ValueError("query must not be empty")
        if start_index < 0:
            raise ValueError("start_index must be non-negative")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        params = {
            "q": query.strip(),
            "lang": language,
            "offset": start_index,
            "limit": limit,
            "fields": ",".join(
                [
                    "key",
                    "title",
                    "author_name",
                    "first_publish_year",
                    "publisher",
                    "number_of_pages_median",
                    "isbn",
                    "language",
                    "cover_i",
                    "subject",
                ]
            ),
        }
        payload = self._get_json(f"{self.settings.open_library_base_url}/search.json", params)
        docs = payload.get("docs") or []
        items = tuple(
            book
            for doc in docs
            if (book := _map_search_doc(doc)) is not None
        )
        return OpenLibraryPage(
            items=items,
            total_items=int(payload.get("numFound", payload.get("num_found", 0))),
            start_index=start_index,
            limit=limit,
        )

    def isbn_lookup(self, isbn: str) -> Book:
        normalized = normalize_isbn(isbn)
        if normalized is None or not (
            validate_isbn10(normalized) or validate_isbn13(normalized)
        ):
            raise ValueError("invalid ISBN")

        payload = self._get_json(
            f"{self.settings.open_library_base_url}/isbn/{normalized}.json",
            {},
        )
        book = _map_edition(payload, normalized)
        if book is None:
            raise OpenLibraryError("Open Library returned no usable edition metadata")
        return book

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"User-Agent": self.settings.user_agent}
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        )
        try:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenLibraryError("Open Library request failed") from exc
        finally:
            if owns_client:
                client.close()
        if not isinstance(payload, dict):
            raise OpenLibraryError("Open Library returned an invalid payload")
        return payload


def _map_search_doc(doc: dict[str, Any]) -> Book | None:
    title = doc.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    isbn10, isbn13 = _pick_isbns(doc.get("isbn") or [])
    language = _first_language(doc.get("language"))
    cover_id = doc.get("cover_i")
    cover_url = (
        f"https://covers.openlibrary.org/b/id/{int(cover_id)}-L.jpg"
        if cover_id is not None
        else None
    )
    source_id = str(doc.get("key", "")).strip("/")

    return Book(
        title=title,
        authors=tuple(doc.get("author_name") or ()),
        publisher=_first(doc.get("publisher")),
        pages=doc.get("number_of_pages_median"),
        publication_year=doc.get("first_publish_year"),
        isbn10=isbn10,
        isbn13=isbn13,
        language=language,
        subjects=tuple(doc.get("subject") or ())[:50],
        cover_url=cover_url,
        source_ids={"open_library": source_id},
    )


def _map_edition(payload: dict[str, Any], requested_isbn: str) -> Book | None:
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    isbn10, isbn13 = _pick_isbns(
        list(payload.get("isbn_10") or ()) + list(payload.get("isbn_13") or ())
    )
    if not isbn10 and len(requested_isbn) == 10:
        isbn10 = requested_isbn
    if not isbn13 and len(requested_isbn) == 13:
        isbn13 = requested_isbn

    authors = tuple(
        author.get("name", "")
        for author in payload.get("authors") or ()
        if isinstance(author, dict) and author.get("name")
    )
    covers = payload.get("covers") or ()
    cover_url = (
        f"https://covers.openlibrary.org/b/id/{int(covers[0])}-L.jpg"
        if covers
        else None
    )

    return Book(
        title=title,
        authors=authors,
        publisher=_first(payload.get("publishers")),
        pages=payload.get("number_of_pages"),
        publication_year=_publication_year(payload.get("publish_date")),
        isbn10=isbn10,
        isbn13=isbn13,
        language=_first_language(payload.get("languages")),
        subjects=tuple(
            subject.get("name", "") if isinstance(subject, dict) else str(subject)
            for subject in payload.get("subjects") or ()
        )[:50],
        cover_url=cover_url,
        source_ids={"open_library": str(payload.get("key", "")).strip("/")},
    )


def _pick_isbns(values: list[Any]) -> tuple[str | None, str | None]:
    isbn10 = isbn13 = None
    for value in values:
        normalized = normalize_isbn(value if isinstance(value, str) else None)
        if normalized and len(normalized) == 10 and validate_isbn10(normalized):
            isbn10 = isbn10 or normalized
        elif normalized and len(normalized) == 13 and validate_isbn13(normalized):
            isbn13 = isbn13 or normalized
    return isbn10, isbn13


def _first(values: Any) -> str | None:
    if isinstance(values, (list, tuple)):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value
    return values if isinstance(values, str) and values.strip() else None


def _first_language(values: Any) -> str | None:
    if isinstance(values, (list, tuple)):
        value = values[0] if values else None
        if isinstance(value, dict):
            key = value.get("key", "")
            return key.rsplit("/", 1)[-1] or None
        return value if isinstance(value, str) else None
    return None


def _publication_year(value: Any) -> int | None:
    if not isinstance(value, str) or len(value) < 4:
        return None
    try:
        year = int(value[-4:])
    except ValueError:
        return None
    return year if 1 <= year <= 9999 else None
