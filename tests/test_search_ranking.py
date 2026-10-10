from books.search_ranking import rank


def test_title_exact_match_has_priority():
    assert rank("شازده کوچولو", title="شازده کوچولو") > rank("شازده کوچولو", authors=("نویسنده",))

def test_zwnj_and_space_are_tolerant():
    assert rank("می روم", title="می‌روم") > 0


def test_rank_book_row_maps_book_rows():
    from books.search_ranking import rank_book_row

    row = {
        "title": "شازده کوچولو",
        "authors_json": '["آنتوان دو سنت‌اگزوپری"]',
        "translators_json": None,
        "publisher": None,
        "isbn13": None,
        "isbn10": None,
    }
    assert rank_book_row("شازده", row) == 1200  # normalized title startswith
    assert rank_book_row("سنت اگزوپری", row) > 0  # author match
    assert rank_book_row("چیز دیگر", row) == 0


def test_relevance_order_differs_from_recency_order(tmp_path):
    from books.db import BookRepository, Database
    from books.models import Book
    from books.search_ranking import rank_book_row

    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    # Oldest: the exact/near title match.
    repo.create_book(Book(title="شازده کوچولو", authors=("آنتوان دو سنت‌اگزوپری",)))
    # Newer: unrelated titles that only match via summary (rank 0).
    repo.create_book(
        Book(title="کتاب اول", authors=("مؤلف اول",), summary="درباره شازده و کوچولو")
    )
    repo.create_book(
        Book(title="کتاب دوم", authors=("مؤلف دوم",), summary="درباره شازده و کوچولو")
    )

    rows = repo.search("شازده", limit=100)
    # Default repository order stays newest-first (unchanged contract).
    assert [row["title"] for row in rows] == ["کتاب دوم", "کتاب اول", "شازده کوچولو"]

    # The two-pass ordering the library page performs: stable newest-first,
    # then a stable relevance sort on top — ties keep the recency order.
    ordered = sorted(
        rows, key=lambda r: (r["updated_at"] or "", r["id"]), reverse=True
    )
    ordered = sorted(ordered, key=lambda r: rank_book_row("شازده", r), reverse=True)
    assert [row["title"] for row in ordered] == [
        "شازده کوچولو",
        "کتاب دوم",
        "کتاب اول",
    ]
