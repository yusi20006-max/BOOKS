from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


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


class DiscoveryService:
    """Provider-agnostic discovery orchestration with deterministic fallback behavior."""

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
        except Exception as exc:
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
            # A successful provider is enough for sequential fallback.
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
