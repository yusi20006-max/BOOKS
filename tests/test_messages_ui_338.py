"""Message-accuracy regressions for issue #338.

User-facing strings must describe what actually happened: the candidate
selection message points to the (existing) confirm page, the enrichment
action distinguishes "metadata updated" from "no new metadata found", and the
delete page's description no longer advertises a duplicate check it does not
perform. Providers are stubbed so the AppTest cases are hermetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from books.models import Book

QUERY_LABEL = "عنوان، نویسنده یا ISBN"


@dataclass
class Page:
    items: tuple
    total_items: int


def _stub(monkeypatch, *, items=()):
    def search(self, *args, **kwargs):
        return Page(tuple(items), len(tuple(items)))

    monkeypatch.setattr(
        "books.providers.google_books.GoogleBooksProvider.search", search
    )
    monkeypatch.setattr(
        "books.providers.open_library.OpenLibraryProvider.search", search
    )


def _values(blocks):
    return [block.value for block in blocks]


# --- enrichment outcome premises (run without streamlit) ---------------------


def test_enrich_returns_input_unchanged_when_providers_return_nothing(tmp_path):
    from books.db import BookRepository, Database
    from books.enrichment import MetadataEnricher

    class EmptyProvider:
        def search(self, *args, **kwargs):
            return Page((), 0)

    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book = Book(title="کتاب آزمون", authors=("نویسنده آزمون",))

    enriched = MetadataEnricher(repo, [("stub", EmptyProvider())]).enrich(book)

    assert enriched == book


def test_enrich_fills_missing_fields_when_a_provider_returns_a_match(tmp_path):
    from books.db import BookRepository, Database
    from books.enrichment import MetadataEnricher

    match = Book(
        title="کتاب آزمون",
        authors=("نویسنده آزمون",),
        summary="خلاصه تازه",
    )

    class MatchProvider:
        def search(self, *args, **kwargs):
            return Page((match,), 1)

    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book = Book(title="کتاب آزمون", authors=("نویسنده آزمون",))

    enriched = MetadataEnricher(repo, [("stub", MatchProvider())]).enrich(book)

    assert enriched != book
    assert enriched.summary == "خلاصه تازه"


# --- AppTest regressions (CI) ------------------------------------------------


def test_candidate_selection_message_points_to_the_confirm_page(
    app_session, monkeypatch
):
    book = Book(title="کتاب آزمون", authors=("نویسنده آزمون",))
    _stub(monkeypatch, items=(book,))
    session = app_session
    session.open("افزودن کتاب")
    session.set_field(QUERY_LABEL, "کتاب آزمون")
    session.click("جستجوی کتاب")
    session.click("انتخاب این کتاب")

    messages = _values(session.at.success)
    assert any("تأیید و ویرایش" in message for message in messages)
    assert not any("Issue" in message for message in messages)


def test_enrichment_reports_no_new_metadata_when_providers_return_nothing(
    app_session, monkeypatch
):
    _stub(monkeypatch, items=())
    session = app_session
    session.seed_book(title="کتاب آزمون", authors=("نویسنده آزمون",))
    session.open("ویرایش کتاب")
    session.click("تکمیل metadata از منابع")

    assert any(
        "metadata جدیدی از منابع پیدا نشد" in message
        for message in _values(session.at.info)
    )
    assert not any("به‌روزرسانی شد" in message for message in _values(session.at.success))


def test_enrichment_success_message_when_metadata_actually_changes(
    app_session, monkeypatch
):
    match = Book(
        title="کتاب آزمون",
        authors=("نویسنده آزمون",),
        summary="خلاصه تازه",
    )
    _stub(monkeypatch, items=(match,))
    session = app_session
    session.seed_book(title="کتاب آزمون", authors=("نویسنده آزمون",))
    session.open("ویرایش کتاب")
    session.click("تکمیل metadata از منابع")

    assert any(
        "به‌روزرسانی شد" in message for message in _values(session.at.success)
    )
    assert not any(
        "metadata جدیدی از منابع پیدا نشد" in message
        for message in _values(session.at.info)
    )


def test_delete_page_description_matches_its_behaviour():
    from books.app import PAGES

    assert PAGES["حذف کتاب"] == "حذف امن کتاب از کتابخانه"
    assert "Duplicate" not in PAGES["حذف کتاب"]
