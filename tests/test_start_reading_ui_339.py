"""UI regression for #339: «شروع مطالعه» must not overwrite the start date."""

from __future__ import annotations

from books.db import BookRepository

BOOK = {
    "title": "شازده کوچولو",
    "authors": ("آنتوان دو سنت‌اگزوپری",),
    "pages": 96,
}


def _book_id(session) -> str:
    return session.repository.list(limit=10)[0]["id"]


def test_start_button_disappears_after_first_start(app_session):
    session = app_session
    session.seed_book(**BOOK)
    session.open("مطالعه")
    session.click("شروع مطالعه")
    assert any(
        message.startswith("شروع مطالعه ثبت شد") for message in session.success_messages()
    )
    book_id = _book_id(session)
    started_at = session.repository.get(book_id)["reading_started_at"]
    assert started_at
    # The repeat press is impossible through the UI: the start button is gone
    # and the recorded date is shown instead.
    assert not any(
        "شروع مطالعه" in (button.label or "") for button in session.at.button
    )
    assert session.repository.get(book_id)["reading_started_at"] == started_at


def test_repeat_start_guard_surfaces_persian_error_without_traceback(
    app_session, monkeypatch
):
    """The repository guard's Persian message reaches the user via st.error."""
    session = app_session
    session.seed_book(**BOOK)
    book_id = _book_id(session)
    real_start = BookRepository.start_reading

    def start_twice(self, target_book_id):
        real_start(self, target_book_id)  # first call persists the timestamp
        return real_start(self, target_book_id)  # second call hits the real guard

    monkeypatch.setattr(BookRepository, "start_reading", start_twice)
    session.open("مطالعه")
    session.click("شروع مطالعه")  # click() asserts no traceback at every step
    assert any(
        "قبلاً شروع شده" in message for message in session.error_messages()
    )
    stored = session.repository.get(book_id)["reading_started_at"]
    assert stored  # the first (intended) timestamp is what remains
