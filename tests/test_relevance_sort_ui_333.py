"""UI regression for issue #333: opt-in relevance sorting on «کتابخانه».

The default order stays «آخرین تغییر» (recency); only when the user picks
«مرتبط‌ترین» do results reorder by search_ranking relevance, with a stable
newest-first tie-break.
"""

from __future__ import annotations

from books.models import Book


def _seed(session) -> None:
    # The exact match is created FIRST, so it is the oldest record.
    session.repository.create_book(
        Book(title="شازده کوچولو", authors=("آنتوان دو سنت‌اگزوپری",))
    )
    session.repository.create_book(
        Book(title="کتاب جدیدتر", authors=("مؤلف دوم",), summary="درباره شازده")
    )


def _subheaders(session) -> list[str]:
    return [block.value for block in session.at.subheader]


def test_relevance_sort_is_opt_in_and_reorders_results(app_session):
    session = app_session
    _seed(session)
    session.open("کتابخانه")
    session.set_field("جستجو در کتابخانه", "شازده")

    # Default sort («آخرین تغییر») is unchanged: the newer unrelated record
    # (summary-only match, rank 0) comes first.
    values = _subheaders(session)
    assert values.index("کتاب جدیدتر") < values.index("شازده کوچولو")

    # Opting into «مرتبط‌ترین» puts the near title match on top.
    session.set_field("مرتب‌سازی", "مرتبط‌ترین")
    values = _subheaders(session)
    assert values.index("شازده کوچولو") < values.index("کتاب جدیدتر")


def test_relevance_sort_without_a_query_keeps_the_default_order(app_session):
    session = app_session
    _seed(session)
    session.open("کتابخانه")
    # «مرتبط‌ترین» selected while browsing (no query) falls back to recency —
    # no crash, no reordering: newest record first.
    session.set_field("مرتب‌سازی", "مرتبط‌ترین")
    assert not session.at.exception

    values = _subheaders(session)
    assert values.index("کتاب جدیدتر") < values.index("شازده کوچولو")
    assert not any("صفحه" in value for value in [b.value for b in session.at.caption])
