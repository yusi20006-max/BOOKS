"""Regression tests for Audit/P2 #355 repository validation gaps."""

import pytest

from books.db import BookRepository, Database
from test_db import book


def _repo(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create(book("b1"))
    return repo


def test_invalid_annotation_rejected(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        repo.add_annotation("", "b1", "highlight", "page:1")
    with pytest.raises(ValueError):
        repo.add_annotation("a1", "b1", "invalid-kind", "page:1")
    with pytest.raises(ValueError):
        repo.add_annotation("a1", "b1", "highlight", "   ")
    with pytest.raises(ValueError):
        repo.add_annotation("a1", "b1", "highlight", 123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        repo.add_annotation("a1", "missing-book", "highlight", "page:1")


def test_invalid_note_quote_rejected(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        repo.add_note("n1", "b1", "   ")
    with pytest.raises(ValueError):
        repo.add_note("n1", "b1", "text", -1)
    with pytest.raises(ValueError):
        repo.add_note("", "b1", "text")
    with pytest.raises(ValueError):
        repo.add_note("n1", "missing", "text")
    with pytest.raises(ValueError):
        repo.add_quote("q1", "b1", "", -2)


def test_invalid_session_rejected(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        repo.add_reading_session("s1", "b1", "not-a-date", 10, 5)
    with pytest.raises(ValueError):
        repo.add_reading_session("s1", "b1", "2026-09-27", -1, 5)
    with pytest.raises(ValueError):
        repo.add_reading_session("", "b1", "2026-09-27", 10, 5)
    with pytest.raises(ValueError):
        repo.add_reading_session("s1", "missing", "2026-09-27", 10, 5)


def test_invalid_copy_rejected(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        repo.add_copy("c1", "b1", condition="moldy")
    with pytest.raises(ValueError):
        repo.add_copy("c1", "b1", status="sold")
    with pytest.raises(ValueError):
        repo.add_copy("", "b1")
    with pytest.raises(ValueError):
        repo.add_copy("c1", "missing")


def test_invalid_loan_and_return_lifecycle(tmp_path):
    repo = _repo(tmp_path)
    repo.add_copy("c1", "b1")
    with pytest.raises(ValueError):
        repo.add_loan("l1", "missing-copy", "br1", "2026-09-27")
    with pytest.raises(ValueError):
        repo.add_loan("", "c1", "br1", "2026-09-27")
    with pytest.raises(ValueError):
        repo.add_loan("l1", "c1", "", "2026-09-27")
    with pytest.raises(ValueError):
        repo.add_loan("l1", "c1", "br1", "bad-date")
    with pytest.raises(ValueError):
        repo.add_loan("l1", "c1", "br1", "2026-09-27", "2026-09-20")
    repo.add_loan("l1", "c1", "br1", "2026-09-27", "2026-10-01")
    assert repo.return_loan("l1", "2026-09-28") is True
    row = repo.list_loans()[0]
    assert row["returned_on"] == "2026-09-28"
    with pytest.raises(ValueError):
        repo.return_loan("l1", "2026-09-29")
    with pytest.raises(ValueError):
        repo.return_loan("missing", "2026-09-28")


def test_copy_model_mapping_documented(tmp_path):
    repo = _repo(tmp_path)
    assert "dual model" in (repo.add_copy.__doc__ or "")
    repo.add_copy("c1", "b1", internal_code="BK-001")
    with repo.db.connect() as conn:
        crow = conn.execute("SELECT * FROM physical_copies WHERE id='c1'").fetchone()
        assert crow["book_id"] == "b1"
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name='copies'").fetchone() is not None
