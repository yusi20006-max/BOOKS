"""Behavioural Streamlit UI tests for display fidelity (issue #342).

The library listing and the edit form must show the user-typed text
(Persian digits, multi-line summary), and an edit-save round trip through
the real UI must not alter it further.
"""

from __future__ import annotations

TITLE = "کتاب آزمون ۱۲۳"
SUMMARY = "خط اول\nخط دوم"
AUTHOR = "نویسندهٔ نمونه"


def _widget_value(session, kind: str, label: str) -> str:
    for widget in getattr(session.at, kind):
        if widget.label == label:
            return widget.value
    raise AssertionError(f"no {kind} widget with label {label!r}")


def test_library_listing_shows_original_persian_digits(app_session):
    session = app_session
    session.seed_book(title=TITLE, authors=(AUTHOR,), summary=SUMMARY)
    session.open("کتابخانه")
    assert TITLE in [block.value for block in session.at.subheader]


def test_edit_form_prefills_original_text(app_session):
    session = app_session
    session.seed_book(title=TITLE, authors=(AUTHOR,), summary=SUMMARY)
    session.open("ویرایش کتاب")
    assert _widget_value(session, "text_input", "عنوان") == TITLE
    assert _widget_value(session, "text_area", "خلاصه") == SUMMARY


def test_edit_save_round_trip_keeps_user_text(app_session):
    session = app_session
    session.seed_book(title=TITLE, authors=(AUTHOR,), summary=SUMMARY)
    session.open("ویرایش کتاب")
    session.set_field("عنوان", "کتاب ویرایش‌شده ۴۵۶")
    session.set_field("خلاصه", "سطر یک\nسطر دو")
    session.click("ذخیره ویرایش")
    assert "ویرایش کتاب با موفقیت ذخیره شد." in session.success_messages()
    row = session.repository.list(limit=10)[0]
    assert row["title"] == "کتاب ویرایش‌شده ۴۵۶"
    assert row["summary"] == "سطر یک\nسطر دو"
