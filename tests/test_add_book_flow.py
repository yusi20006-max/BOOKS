"""Widget-level regression tests for the Add Book flow (issue #319).

The save action must run in its own Streamlit run: Streamlit form-submit
buttons are trigger values that reset to False after the submitting run, so
the save button can only be honoured when the validated candidate is read
from persistent session state instead of being gated behind ``if submitted:``.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import books.app as books_app
from books.db import BookRepository, Database
from books.models import Book

APP_SCRIPT = "from books.app import main\n\nmain()\n"

BOOK = Book(
    title="کتاب آزمون",
    authors=("نویسنده آزمون",),
    translators=("مترجم آزمون",),
    publisher="نشر آزمون",
    pages=250,
    publication_year=1400,
    isbn13="9780306406157",
    language="fa",
    genres=("رمان",),
    subjects=("ادبیات",),
    summary="خلاصه آزمون",
    cover_url="https://example.invalid/cover.jpg",
    source_ids={"google_books": "audit-1"},
    notes="یادداشت آزمون",
)


@pytest.fixture()
def app(monkeypatch, tmp_path):
    db_path = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    monkeypatch.setattr(books_app.GoogleBooksProvider, "__init__", lambda self, settings: None)
    monkeypatch.setattr(
        books_app.GoogleBooksProvider, "search",
        lambda self, query, *, language, start_index, limit: SimpleNamespace(items=(BOOK,), total_items=1),
    )
    monkeypatch.setattr(books_app.OpenLibraryProvider, "__init__", lambda self, settings: None)
    monkeypatch.setattr(
        books_app.OpenLibraryProvider, "search",
        lambda self, query, *, language, start_index, limit: SimpleNamespace(items=(), total_items=0),
    )
    at = AppTest.from_string(APP_SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception
    assert os.environ["BOOKS_DB_PATH"] == str(db_path)
    return at

def _go(at: AppTest, page: str) -> AppTest:
    at.sidebar.radio[0].set_value(page)
    at.run()
    return at


def _submit(at: AppTest, label_fragment: str) -> None:
    matches = [button for button in at.button if label_fragment in (button.label or "")]
    assert matches, f"button containing {label_fragment!r} not found"
    matches[0].click()
    at.run()


def _search_and_select(at: AppTest) -> None:
    _go(at, "افزودن کتاب")
    at.text_input[0].set_value("کتاب آزمون")
    at.run()
    _submit(at, "جستجوی کتاب")
    select = [button for button in at.button if (button.label or "").startswith("انتخاب")]
    assert len(select) == 1
    select[0].click()
    at.run()
    assert at.session_state.get("selected_candidate") is not None


def _repository() -> BookRepository:
    return BookRepository(Database(os.environ["BOOKS_DB_PATH"]))


def test_save_flow_creates_book_with_structured_fields(app):
    at = app
    _search_and_select(at)

    _go(at, "تأیید و ویرایش")
    assert not at.exception
    _submit(at, "اعتبارسنجی و پیش‌نمایش")
    assert "اطلاعات معتبر است و پیش‌نمایش آماده شد." in [message.value for message in at.success]
    assert at.session_state.get("edited_candidate") is not None

    _go(at, "کتابخانه")
    _go(at, "تأیید و ویرایش")
    _submit(at, "ذخیره کتاب در کتابخانه")
    assert not at.exception
    assert "کتاب با موفقیت در SQLite ذخیره شد." in [message.value for message in at.success]

    rows = _repository().list(limit=100)
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "کتاب آزمون"
    assert row["authors_json"] == '["نویسنده آزمون"]'
    assert row["translators_json"] == '["مترجم آزمون"]'
    assert row["isbn13"] == "9780306406157"
    assert row["genres_json"] == '["رمان"]'
    assert row["subjects_json"] == '["ادبیات"]'
    assert row["source_ids_json"] == '{"google_books": "audit-1"}'
    assert row["notes"] == "یادداشت آزمون"
    assert at.session_state.get("saved_book_id") == row["id"]


def test_save_flow_is_idempotent_for_duplicates(app):
    at = app
    _search_and_select(at)

    _go(at, "تأیید و ویرایش")
    _submit(at, "اعتبارسنجی و پیش‌نمایش")
    _submit(at, "ذخیره کتاب در کتابخانه")
    assert "کتاب با موفقیت در SQLite ذخیره شد." in [message.value for message in at.success]
    assert len(_repository().list(limit=100)) == 1

    at.run()
    _submit(at, "ذخیره کتاب در کتابخانه")
    assert "کتاب مشابهی در کتابخانه پیدا شد؛ ابتدا نتیجه را بررسی کنید." in [
        message.value for message in at.warning
    ]
    assert len(_repository().list(limit=100)) == 1


def test_save_flow_rejects_invalid_isbn_without_writing(app):
    at = app
    _search_and_select(at)

    _go(at, "تأیید و ویرایش")
    _submit(at, "اعتبارسنجی و پیش‌نمایش")
    inputs = {field.label: field for field in at.text_input}
    inputs["ISBN-13"].set_value("invalid-isbn")
    at.run()
    _submit(at, "اعتبارسنجی و پیش‌نمایش")
    assert "اطلاعات واردشده معتبر نیست" in "".join(message.value for message in at.error)
    assert not _repository().list(limit=100)


def test_selecting_new_candidate_discards_previous_validation(app):
    at = app
    _search_and_select(at)

    _go(at, "تأیید و ویرایش")
    _submit(at, "اعتبارسنجی و پیش‌نمایش")
    assert at.session_state.get("edited_candidate") is not None

    _go(at, "افزودن کتاب")
    select = [button for button in at.button if (button.label or "").startswith("انتخاب")]
    assert len(select) == 1
    select[0].click()
    at.run()
    assert at.session_state.get("edited_candidate") is None
    assert at.session_state.get("saved_book_id") is None
