"""Widget-level regression tests for the loans page (issue #320).

Empty copy/borrower ids must be rejected with a Persian error and no
write; repeating a registered copy id must surface a Persian error
instead of a raw sqlite3.IntegrityError traceback.
"""

from __future__ import annotations

import os

import pytest
from streamlit.testing.v1 import AppTest

from books.db import BookRepository, Database
from books.models import Book

APP_SCRIPT = "from books.app import main\n\nmain()\n"


@pytest.fixture()
def app(monkeypatch, tmp_path):
    db_path = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    repository = BookRepository(Database(db_path))
    repository.db.migrate()
    repository.create_book(Book(title="کتاب امانت", authors=("نویسنده",), pages=100))
    at = AppTest.from_string(APP_SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception
    at.sidebar.radio[0].set_value("قرض‌ها")
    at.run()
    assert not at.exception
    return at


def _register(at: AppTest, copy_id: str, borrower: str) -> None:
    inputs = {field.label: field for field in at.text_input}
    inputs["شناسه نسخه"].set_value(copy_id)
    at.run()
    inputs = {field.label: field for field in at.text_input}
    inputs["شناسه امانت‌گیرنده"].set_value(borrower)
    at.run()
    matches = [button for button in at.button if "ثبت نسخه و امانت" in (button.label or "")]
    assert matches
    matches[0].click()
    at.run()


def _repository() -> BookRepository:
    return BookRepository(Database(os.environ["BOOKS_DB_PATH"]))


def test_empty_copy_and_borrower_rejected_without_writing(app):
    at = app
    _register(at, "   ", "")
    assert not at.exception
    errors = [message.value for message in at.error]
    assert any("شناسه نسخه" in message for message in errors)
    assert not _repository().list_loans()
    _register(at, "copy-ok", "   ")
    errors = [message.value for message in at.error]
    assert any("امانت‌گیرنده" in message for message in errors)
    assert not _repository().list_loans()


def test_valid_registration_writes_once(app):
    at = app
    _register(at, "copy-1", "borrower-1")
    assert not at.exception
    assert "نسخه و امانت در SQLite ثبت شد." in [message.value for message in at.success]
    repository = _repository()
    loans = repository.list_loans()
    copies = repository.db.connect().execute("SELECT * FROM physical_copies").fetchall()
    assert len(loans) == 1
    assert len(copies) == 1
    assert loans[0]["copy_id"] == "copy-1"
    assert loans[0]["borrower_id"] == "borrower-1"


def test_duplicate_copy_id_shows_error_without_traceback(app):
    at = app
    _register(at, "copy-1", "borrower-1")
    assert "نسخه و امانت در SQLite ثبت شد." in [message.value for message in at.success]
    _register(at, "copy-1", "borrower-2")
    assert not at.exception
    errors = [message.value for message in at.error]
    assert any("قبلاً ثبت شده" in message for message in errors)
    assert len(_repository().list_loans()) == 1
