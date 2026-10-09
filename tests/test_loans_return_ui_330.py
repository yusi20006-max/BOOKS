"""UI regression for issue #330: the loans return workflow.

«قرض‌ها» must offer a return action for active loans (reusing the existing
``BookRepository.return_loan``), flag overdue/due-soon loans via
``books.lending.due_state`` and keep showing book/copy context.
"""

from __future__ import annotations

from datetime import date, timedelta

from books.models import Book

BOOK = {"title": "شازده کوچولو", "authors": ("آنتوان دو سنت‌اگزوپری",), "pages": 96}


def _seed_active_loan(session, *, due_on: str) -> str:
    repo = session.repository
    book_id = repo.create_book(Book(**BOOK))
    repo.add_copy("copy-1", book_id)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", due_on)
    return book_id


def _copy_status(session, copy_id: str) -> str:
    with session.repository.db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM physical_copies WHERE id = ?", (copy_id,)
        ).fetchone()
    return row["status"]


def test_overdue_loan_is_flagged_and_can_be_returned(app_session):
    session = app_session
    _seed_active_loan(session, due_on="2026-09-25")
    session.open("قرض‌ها")
    captions = [block.value for block in session.at.caption]
    assert any("امانت‌های فعال: 1 | در موعد گذشته: 1" in caption for caption in captions)
    assert _copy_status(session, "copy-1") == "on_loan"

    session.click("ثبت بازگشت نسخه")
    assert any("بازگشت نسخه ثبت شد" in message for message in session.success_messages())
    loan = session.repository.list_loans()[0]
    assert loan["returned_on"] == date.today().isoformat()
    assert _copy_status(session, "copy-1") == "available"


def test_due_soon_loan_is_flagged(app_session):
    session = app_session
    soon = (date.today() + timedelta(days=3)).isoformat()
    _seed_active_loan(session, due_on=soon)
    session.open("قرض‌ها")
    captions = [block.value for block in session.at.caption]
    assert any("نزدیک سررسید: 1" in caption for caption in captions)


def test_return_selectbox_offers_only_active_loans(app_session):
    session = app_session
    far = (date.today() + timedelta(days=30)).isoformat()
    _seed_active_loan(session, due_on=far)
    session.open("قرض‌ها")
    selectboxes = {box.label: box for box in session.at.selectbox}
    assert "امانت برای بازگشت" in selectboxes
    assert list(selectboxes["امانت برای بازگشت"].options) == ["loan-1"]

    session.click("ثبت بازگشت نسخه")
    session.open("قرض‌ها")
    selectboxes = {box.label: box for box in session.at.selectbox}
    assert "امانت برای بازگشت" not in selectboxes  # nothing active anymore
