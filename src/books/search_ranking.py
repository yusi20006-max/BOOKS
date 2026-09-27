from __future__ import annotations

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
