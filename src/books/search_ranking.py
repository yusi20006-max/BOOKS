from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .normalization import normalize_text


def score(query: str, value: str, weight: int = 1) -> int:
    q = normalize_text(query).replace("\u200c", " ")
    v = normalize_text(value).replace("\u200c", " ")
    if not q or not v: return 0
    if v == q: return weight * 130
    if v.startswith(q): return weight * 120
    if q in v: return weight * 100
    return 0

def rank(query: str, *, title: str = "", authors=(), translators=(), publisher: str = "", isbn: str = "") -> int:
    return max(score(query,title,10), max((score(query,x,8) for x in authors), default=0), max((score(query,x,7) for x in translators), default=0), score(query,publisher,5), score(query,isbn,4))


def rank_book_row(query: str, row: Mapping[str, Any]) -> int:
    """Relevance of a ``books`` table row (sqlite3.Row or dict) for a query."""
    return rank(
        query,
        title=row["title"] or "",
        authors=tuple(json.loads(row["authors_json"] or "[]")),
        translators=tuple(json.loads(row["translators_json"] or "[]")),
        publisher=row["publisher"] or "",
        isbn=row["isbn13"] or row["isbn10"] or "",
    )
