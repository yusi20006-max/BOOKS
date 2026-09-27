from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .models import Book


class PersianMetadataProvider(Protocol):
    """Optional provider contract for Persian/IR bibliographic sources."""
    name: str

    def search(self, query: str, *, limit: int = 10) -> Iterable[Book]: ...


@dataclass(frozen=True, slots=True)
class PersianProviderRegistry:
    """Keeps Persian providers out of UI and core discovery implementation."""
    providers: tuple[PersianMetadataProvider, ...] = ()

    def __post_init__(self) -> None:
        names = [p.name for p in self.providers]
        if len(names) != len(set(names)):
            raise ValueError("Persian provider names must be unique")

    def search(self, query: str, *, limit: int = 10) -> tuple[Book, ...]:
        if not query.strip() or limit < 1:
            return ()
        results: list[Book] = []
        for provider in self.providers:
            try:
                results.extend(provider.search(query, limit=limit))
            except Exception:
                # One optional Persian source must not make other sources unavailable.
                continue
            if len(results) >= limit:
                break
        return tuple(results[:limit])
