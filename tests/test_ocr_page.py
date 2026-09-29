"""Widget-level regression tests for the OCR page (issue #329).

An empty title, an invalid ISBN and a duplicate ISBN must produce
Persian messages with no writes and no raw sqlite3/ValueError traceback.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from books.db import BookRepository, Database
from books.models import Book

APP_SCRIPT = "from books.app import main\n\nmain()\n"
ISBN = "9780306406157"


@pytest.fixture()
def app(monkeypatch, tmp_path):
    db_path = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    repository = BookRepository(Database(db_path))
    repository.db.migrate()
    repository.create_book(Book(title="کتاب موجود", authors=("نویسنده",), isbn13=ISBN))
    at = AppTest.from_string(APP_SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception
    at.sidebar.radio[0].set_value("اسکن و OCR")
    at.run()
    assert not at.exception
    return at


def _save(at: AppTest, title: str, publisher: str, isbn: str) -> None:
    inputs = {field.label: field for field in at.text_area}
    inputs["متن OCR یا صفحه مشخصات کتاب"].set_value("متن نمونه")
    at.run()
    inputs = {field.label: field for field in at.text_input}
    inputs["عنوان اصلاح‌شده"].set_value(title)
    inputs["ناشر اصلاح‌شده"].set_value(publisher)
    inputs["ISBN اصلاح‌شده"].set_value(isbn)
    at.run()
    matches = [button for button in at.button if "ذخیره نتیجه OCR" in (button.label or "")]
    assert matches
    matches[0].click()
    at.run()


def _count() -> int:
    import os

    return len(BookRepository(Database(os.environ["BOOKS_DB_PATH"])).list(limit=100))


def test_empty_title_rejected(app):
    _save(app, "   ", "ناشر", ISBN)
    assert not app.exception
    assert any("عنوان اصلاح‌شده" in message for message in [m.value for m in app.error])
    assert _count() == 1


def test_invalid_isbn_rejected(app):
    _save(app, "کتاب تازه", "ناشر", "1234567890123")
    assert not app.exception
    assert any("معتبر نیست" in message for message in [m.value for m in app.error])
    assert _count() == 1


def test_duplicate_isbn_warns_without_traceback(app):
    _save(app, "کتاب تازه", "ناشر تازه", ISBN)
    assert not app.exception
    assert any("مشابهی در کتابخانه" in message for message in [m.value for m in app.warning])
    assert _count() == 1


def test_valid_unique_draft_saved(app):
    _save(app, "کتاب تازه", "ناشر تازه", "9780262033848")
    assert not app.exception
    assert "نتیجه OCR پس از اصلاح در SQLite ذخیره شد." in [m.value for m in app.success]
    assert _count() == 2
