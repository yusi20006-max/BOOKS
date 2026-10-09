"""Shared fixture for behavioural Streamlit UI tests (issue #337).

``app_session`` renders the real application (``books.app.main``) through
``streamlit.testing.v1.AppTest`` against a temporary ``BOOKS_DB_PATH`` and
exposes small helpers to navigate pages and drive widgets by their visible
label, so behavioural tests read like the user workflow they cover.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

APP_SCRIPT = "from books.app import main\n\nmain()\n"
APP_TIMEOUT = 30


class AppSession:
    """An AppTest session bound to a temporary database."""

    def __init__(self, at, db_path: Path) -> None:
        self.at = at
        self.db_path = Path(db_path)

    @property
    def repository(self):
        from books.db import BookRepository, Database

        return BookRepository(Database(self.db_path))

    def seed_book(self, **kwargs: Any) -> None:
        """Insert a book directly through the repository (no UI, no network)."""
        from books.models import Book

        self.repository.create_book(Book(**kwargs))

    def open(self, page: str | None = None):
        """Navigate to a sidebar page (or re-run) and assert a clean render."""
        if page is not None:
            self.at.sidebar.radio[0].set_value(page)
        self.at.run()
        assert not self.at.exception, self.at.exception
        return self.at

    def set_field(self, label: str, value: Any):
        """Set a widget by its visible label across the common widget kinds."""
        for kind in ("text_input", "text_area"):
            for widget in getattr(self.at, kind):
                if widget.label == label:
                    widget.set_value(str(value))
                    self.at.run()
                    assert not self.at.exception, self.at.exception
                    return self.at
        for widget in self.at.number_input:
            if widget.label == label:
                widget.set_value(value)
                self.at.run()
                assert not self.at.exception, self.at.exception
                return self.at
        for kind in ("selectbox", "radio"):
            for widget in getattr(self.at, kind):
                if widget.label == label:
                    widget.set_value(value)
                    self.at.run()
                    assert not self.at.exception, self.at.exception
                    return self.at
        for widget in self.at.checkbox:
            if widget.label == label:
                widget.set_value(bool(value))
                self.at.run()
                assert not self.at.exception, self.at.exception
                return self.at
        for widget in self.at.date_input:
            if widget.label == label:
                widget.set_value(value)
                self.at.run()
                assert not self.at.exception, self.at.exception
                return self.at
        raise AssertionError(f"no widget with label {label!r} on the current page")

    def click(self, label: str):
        """Click the (form submit) button whose label contains ``label``."""
        matches = [button for button in self.at.button if label in (button.label or "")]
        assert matches, f"button containing {label!r} not found"
        matches[0].click()
        self.at.run()
        assert not self.at.exception, self.at.exception
        return self.at

    def success_messages(self) -> list[str]:
        return [block.value for block in self.at.success]

    def error_messages(self) -> list[str]:
        return [block.value for block in self.at.error]

    def info_messages(self) -> list[str]:
        return [block.value for block in self.at.info]

    def warning_messages(self) -> list[str]:
        return [block.value for block in self.at.warning]


@pytest.fixture()
def app_session(monkeypatch, tmp_path) -> AppSession:
    """Render the real app once against a temporary database."""
    from streamlit.testing.v1 import AppTest

    db_path = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    at = AppTest.from_string(APP_SCRIPT, default_timeout=APP_TIMEOUT)
    at.run()
    assert not at.exception, at.exception
    return AppSession(at, db_path)
