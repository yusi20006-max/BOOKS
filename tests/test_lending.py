"""Domain and repository tests for the lending workflow (issue #330).

Covers ``books.lending`` (``Loan.status``, ``due_state``, ``Acquisition``
validation) — previously untested — plus the repository operations behind the
«قرض‌ها» return workflow: copy status transitions, the active-loan guard and
the contextual loan queries.
"""

from __future__ import annotations

from datetime import date

import pytest

from books.db import BookRepository, Database
from books.lending import Acquisition, Loan, due_state
from books.models import Book


def _repo(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    return BookRepository(db)


def _seed_copy(repo):
    book_id = repo.create_book(Book(title="کتاب امانت", authors=("نویسنده",)))
    repo.add_copy("copy-1", book_id)
    return book_id


def _loan(**overrides):
    values = {
        "copy_id": "copy-1",
        "borrower_id": "borrower-1",
        "loaned_on": date(2026, 9, 1),
    }
    values.update(overrides)
    return Loan(**values)


def _copy_status(repo, copy_id: str) -> str:
    with repo.db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM physical_copies WHERE id = ?", (copy_id,)
        ).fetchone()
    return row["status"]


# --- books.lending domain (previously 0% coverage) ---------------------------


def test_loan_status_reflects_return():
    assert _loan().status == "active"
    assert _loan(returned_on=date(2026, 9, 10)).status == "returned"


def test_due_state_branches():
    today = date(2026, 10, 9)
    assert due_state(_loan(returned_on=date(2026, 9, 10)), today) == "returned"
    assert due_state(_loan(due_on=None), today) == "no_due_date"
    assert due_state(_loan(due_on=date(2026, 10, 8)), today) == "overdue"
    assert due_state(_loan(due_on=date(2026, 10, 12)), today) == "due_soon"
    assert due_state(_loan(due_on=date(2026, 10, 16)), today) == "due_soon"  # exactly 7 days
    assert due_state(_loan(due_on=date(2026, 10, 17)), today) == "active"


def test_acquisition_validation():
    with pytest.raises(ValueError):
        Acquisition(copy_id="   ")
    with pytest.raises(ValueError):
        Acquisition(copy_id="copy-1", price=-1)
    assert Acquisition(copy_id="copy-1", price=12.5).price == 12.5


# --- repository: copy status lifecycle ---------------------------------------


def test_loan_marks_copy_on_loan_and_return_restores_available(tmp_path):
    repo = _repo(tmp_path)
    _seed_copy(repo)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", "2026-10-01")
    assert _copy_status(repo, "copy-1") == "on_loan"
    assert repo.return_loan("loan-1", "2026-10-02") is True
    assert _copy_status(repo, "copy-1") == "available"
    assert repo.list_loans()[0]["returned_on"] == "2026-10-02"


def test_second_active_loan_for_same_copy_is_rejected(tmp_path):
    repo = _repo(tmp_path)
    _seed_copy(repo)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", "2026-10-01")
    with pytest.raises(ValueError) as excinfo:
        repo.add_loan("loan-2", "copy-1", "borrower-2", "2026-09-02")
    assert "هم‌اکنون امانت" in str(excinfo.value)
    assert len(repo.list_loans()) == 1


def test_copy_can_be_lent_again_after_return(tmp_path):
    repo = _repo(tmp_path)
    _seed_copy(repo)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", "2026-10-01")
    repo.return_loan("loan-1", "2026-10-02")
    repo.add_loan("loan-2", "copy-1", "borrower-2", "2026-10-03", "2026-10-20")
    assert [row["id"] for row in repo.list_active_loans()] == ["loan-2"]


def test_returning_twice_is_rejected_persian_and_changes_nothing(tmp_path):
    repo = _repo(tmp_path)
    _seed_copy(repo)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", "2026-10-01")
    repo.return_loan("loan-1", "2026-10-02")
    with repo.db.connect() as conn:
        before = dict(conn.execute("SELECT * FROM loans WHERE id='loan-1'").fetchone())
    with pytest.raises(ValueError) as excinfo:
        repo.return_loan("loan-1", "2026-10-05")
    assert "قبلاً بازگردانده" in str(excinfo.value)
    with repo.db.connect() as conn:
        after = dict(conn.execute("SELECT * FROM loans WHERE id='loan-1'").fetchone())
    assert after == before
    assert _copy_status(repo, "copy-1") == "available"


# --- contextual queries ------------------------------------------------------


def test_contextual_queries_expose_book_and_copy(tmp_path):
    repo = _repo(tmp_path)
    book_id = _seed_copy(repo)
    repo.add_loan("loan-1", "copy-1", "borrower-1", "2026-09-01", "2026-10-01")
    active = repo.list_active_loans()
    assert len(active) == 1
    assert active[0]["book_id"] == book_id
    assert active[0]["book_title"] == "کتاب امانت"
    assert active[0]["copy_status"] == "on_loan"
    repo.return_loan("loan-1", "2026-10-02")
    assert repo.list_active_loans() == []
    detailed = repo.list_loans_detailed()
    assert len(detailed) == 1
    assert detailed[0]["book_title"] == "کتاب امانت"
    assert detailed[0]["copy_status"] == "available"
    assert detailed[0]["returned_on"] == "2026-10-02"
