"""Regression for issue #343: the library must not silently cap at 1000 rows.

Repository tests (local): counts and offset paging reach every book, and
filters share one result set with paging. UI tests (CI): the header shows
visible-of-total, the pager reaches later pages, and the book selectors stay
searchable beyond the row cap.
"""

from __future__ import annotations

from books.db import BookRepository, Database
from books.models import Book


def _repo(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    return BookRepository(db)


def _seed_many(repo, count: int) -> None:
    for index in range(count):
        repo.create_book(
            Book(
                title=f"کتاب {index:04d}",
                authors=("نویسنده",),
                publisher="ناشر الف" if index % 2 == 0 else "ناشر ب",
            )
        )


def test_counts_and_paging_reach_every_book(tmp_path):
    repo = _repo(tmp_path)
    _seed_many(repo, 1001)

    assert repo.count() == 1001
    assert repo.filter_count() == 1001
    assert repo.filter_count(publisher="ناشر الف") == 501
    assert repo.filter_count(publisher="ناشر ناشناس") == 0

    # Walking the pages via the existing offset contract reaches every book.
    seen: set[str] = set()
    offset = 0
    while True:
        page = repo.filter_books(limit=100, offset=offset)
        if not page:
            break
        seen.update(row["id"] for row in page)
        offset += 100
    assert len(seen) == 1001

    # Filters and paging share one result set: every paged row matches.
    matched: set[str] = set()
    offset = 0
    while True:
        page = repo.filter_books(publisher="ناشر الف", limit=100, offset=offset)
        if not page:
            break
        assert all(row["publisher"] == "ناشر الف" for row in page)
        matched.update(row["id"] for row in page)
        offset += 100
    assert len(matched) == 501

    # Search uses the same limit/offset contract.
    found = {row["id"] for row in repo.search("کتاب 1000", limit=100)}
    assert len(found) == 1


def test_filter_count_matches_filter_books_for_small_libraries(tmp_path):
    repo = _repo(tmp_path)
    repo.create_book(Book(title="الف", authors=("یک",), publisher="ناشر الف"))
    repo.create_book(Book(title="ب", authors=("دو",), publisher="ناشر ب"))

    assert repo.count() == 2
    assert repo.filter_count() == 2
    assert repo.filter_count(publisher="ناشر الف") == 1
    assert repo.filter_count(publisher="ناشر ناشناس") == 0


# --- AppTest regressions (CI) ------------------------------------------------


def test_library_header_shows_visible_of_total_and_pages_reach_the_last_book(
    app_session,
):
    session = app_session
    _seed_many(session.repository, 1001)
    session.open("کتابخانه")

    assert "100 از 1001 کتاب" in [block.value for block in session.at.subheader]
    session.click("صفحه بعدی")
    assert any("صفحه 2 از 11" in block.value for block in session.at.caption)

    # The last page exposes the final book — nothing is silently unreachable.
    session.at.session_state["library_page"] = 10
    session.open("کتابخانه")
    titles = [block.value for block in session.at.subheader]
    assert "کتاب 1000" in titles


def test_small_library_keeps_the_single_page_behaviour(app_session):
    session = app_session
    session.seed_book(title="کتاب اول", authors=("نویسنده",))
    session.seed_book(title="کتاب دوم", authors=("نویسنده",))
    session.open("کتابخانه")

    # Unchanged behaviour at/below the cap: exact header, no pager.
    assert "2 کتاب" in [block.value for block in session.at.subheader]
    buttons = [button.label for button in session.at.button]
    assert "صفحه قبلی" not in buttons
    assert "صفحه بعدی" not in buttons


def test_edit_selector_searches_beyond_the_row_cap(app_session):
    session = app_session
    _seed_many(session.repository, 1001)
    session.open("ویرایش کتاب")

    assert any(
        field.label == "جستجوی کتاب برای انتخاب" for field in session.at.text_input
    )
    boxes = {box.label: box for box in session.at.selectbox}
    assert "کتاب" in boxes

    session.set_field("جستجوی کتاب برای انتخاب", "کتاب 1000")
    boxes = {box.label: box for box in session.at.selectbox}
    assert list(boxes["کتاب"].options) == ["کتاب 1000"]
