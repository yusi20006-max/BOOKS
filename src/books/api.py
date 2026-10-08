from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any

from . import __version__
from .db import BookRepository


def serialize_book_row(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Map a storage row to the public API shape.

    Keeps raw ``*_json`` columns for backward compatibility while adding
    parsed ``authors/translators/genres/subjects`` (lists) and
    ``source_ids`` (dict). Malformed JSON degrades to ``[]``/``{}``.
    """
    data = dict(row)
    for field in ("authors", "translators", "genres", "subjects"):
        raw = data.get(f"{field}_json")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        except (ValueError, TypeError):
            parsed = []
        data[field] = list(parsed) if isinstance(parsed, list) else []
    try:
        source_ids = json.loads(data.get("source_ids_json") or "{}")
    except (ValueError, TypeError):
        source_ids = {}
    data["source_ids"] = dict(source_ids) if isinstance(source_ids, dict) else {}
    return data


@dataclass(slots=True)
class RateLimiter:
    limit: int = 60
    window: float = 60.0
    hits: dict[str, list[float]] | None = None

    def __post_init__(self) -> None:
        self.hits = {} if self.hits is None else self.hits

    def allow(self, key: str) -> bool:
        now = monotonic()
        values = [x for x in self.hits.get(key, []) if now - x < self.window]
        if len(values) >= self.limit:
            self.hits[key] = values
            return False
        values.append(now)
        self.hits[key] = values
        return True


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class BooksAPI:
    def __init__(
        self,
        repo: BookRepository,
        token: str | None = None,
        limiter: RateLimiter | None = None,
    ):
        self.repo = repo
        self.token = token
        self.limiter = limiter or RateLimiter()

    def authorize(self, provided: str | None) -> None:
        if self.token is not None and provided != self.token:
            raise APIError(401, "unauthorized")

    def check_rate_limit(self, client_id: str) -> None:
        if not self.limiter.allow(client_id):
            raise APIError(429, "rate limit exceeded")

    @staticmethod
    def _pagination(query: dict[str, str]) -> tuple[int, int]:
        try:
            limit = int(query.get("limit", 100))
            offset = int(query.get("offset", 0))
        except ValueError as exc:
            raise APIError(400, "limit and offset must be integers") from exc
        if not 1 <= limit <= 100:
            raise APIError(400, "limit must be between 1 and 100")
        if offset < 0:
            raise APIError(400, "offset must be non-negative")
        return limit, offset

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        query: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        client_id: str = "local",
    ):
        self.authorize(token)
        self.check_rate_limit(client_id)
        query = query or {}
        body = body or {}
        if method == "GET" and path == "/v1/books":
            limit, offset = self._pagination(query)
            return [serialize_book_row(x) for x in self.repo.list(limit, offset)]
        if method == "GET" and path == "/v1/search":
            limit, offset = self._pagination(query)
            return [serialize_book_row(x) for x in self.repo.search(query.get("q", ""), limit, offset)]
        if method == "GET" and path.startswith("/v1/books/"):
            row = self.repo.get(path.rsplit("/", 1)[1])
            if row is None:
                raise APIError(404, "book not found")
            return serialize_book_row(row)
        raise APIError(404, "endpoint not found")

    @staticmethod
    def openapi() -> dict[str, Any]:
        return {
            "openapi": "3.0.3",
            "info": {"title": "BOOKS API", "version": __version__},
            "servers": [{"url": "/"}],
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                },
                "schemas": {
                    "Error": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {"error": {"type": "string"}},
                    }
                },
            },
            "paths": {
                "/health": {"get": {"parameters": [{"name": "deep", "in": "query", "schema": {"type": "string"}, "description": "Set to 1 for a readiness check validating the full database schema (503 with missing tables when degraded). Without it, a cheap liveness probe."}], "responses": {"200": {"description": "Healthy"}, "503": {"description": "Degraded (deep check only)"}}}},
                "/openapi.json": {"get": {"responses": {"200": {"description": "OpenAPI document"}}}},
                "/v1/books": {
                    "get": {
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100}},
                            {"name": "offset", "in": "query", "schema": {"type": "integer", "minimum": 0}},
                        ],
                        "responses": {
                            "200": {"description": "Books"},
                            "401": {"description": "Unauthorized"},
                            "429": {"description": "Rate limited"},
                        },
                    }
                },
                "/v1/books/{id}": {
                    "get": {
                        "security": [{"bearerAuth": []}],
                        "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "Book"}, "401": {"description": "Unauthorized"}, "404": {"description": "Not found"}},
                    }
                },
                "/v1/search": {
                    "get": {
                        "security": [{"bearerAuth": []}],
                        "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "Search results"}, "401": {"description": "Unauthorized"}, "429": {"description": "Rate limited"}},
                    }
                },
            },
        }
