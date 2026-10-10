"""UI regression for issue #322: «افزودن کتاب» feedback states.

The discovery page must distinguish (a) no search yet, (b) a completed search
with zero results, and (c) provider failures — naming the failed providers and
keeping the page usable offline. Providers are stubbed at class level so the
tests are hermetic (no network).
"""

from __future__ import annotations

from dataclasses import dataclass

from books.models import Book
from books.providers.google_books import GoogleBooksProvider
from books.providers.open_library import OpenLibraryProvider

QUERY_LABEL = "عنوان، نویسنده یا ISBN"


@dataclass
class EmptyPage:
    items: tuple = ()
    total_items: int = 0


def _stub(monkeypatch, *, google=None, open_library=None):
    monkeypatch.setattr(
        GoogleBooksProvider,
        "search",
        google or (lambda self, *args, **kwargs: EmptyPage()),
    )
    monkeypatch.setattr(
        OpenLibraryProvider,
        "search",
        open_library or (lambda self, *args, **kwargs: EmptyPage()),
    )


def _search(session, query="کتاب آزمون"):
    session.set_field(QUERY_LABEL, query)
    session.click("جستجوی کتاب")
    return session


def _values(blocks):
    return [block.value for block in blocks]


def test_initial_hint_shows_before_any_search(app_session):
    session = app_session
    session.open("افزودن کتاب")
    assert any("برای شروع" in message for message in _values(session.at.info))


def test_all_providers_failing_shows_warning_naming_them(app_session, monkeypatch):
    def boom(self, *args, **kwargs):
        raise RuntimeError("اتصال برقرار نشد")

    _stub(monkeypatch, google=boom, open_library=boom)
    session = app_session
    session.open("افزودن کتاب")
    _search(session)

    warnings = _values(session.at.warning)
    assert any("google_books" in message and "open_library" in message for message in warnings)
    # The failure state must not masquerade as "no results" or as the
    # untouched initial state.
    infos = _values(session.at.info)
    assert not any("نتیجه‌ای یافت نشد" in message for message in infos)
    assert not any("برای شروع" in message for message in infos)


def test_completed_search_without_matches_shows_no_results(app_session, monkeypatch):
    _stub(monkeypatch)
    session = app_session
    session.open("افزودن کتاب")
    _search(session)

    assert any("نتیجه‌ای یافت نشد" in message for message in _values(session.at.info))
    assert len(session.at.warning) == 0
    assert not any("برای شروع" in message for message in _values(session.at.info))


def test_partial_results_render_items_plus_warning(app_session, monkeypatch):
    book = Book(title="کتاب آزمون", authors=("نویسنده آزمون",))

    @dataclass
    class OnePage:
        items: tuple = (book,)
        total_items: int = 1

    def one(self, *args, **kwargs):
        return OnePage()

    def boom(self, *args, **kwargs):
        raise RuntimeError("offline")

    _stub(monkeypatch, google=one, open_library=boom)
    session = app_session
    session.open("افزودن کتاب")
    _search(session)

    assert "1 نتیجه" in _values(session.at.subheader)
    assert any("open_library" in message for message in _values(session.at.warning))
