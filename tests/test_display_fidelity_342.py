"""Display-fidelity regression tests (issue #342).

Policy: text columns store the user-typed text (Persian digits, ZWNJ,
line breaks preserved); the canonical form from ``normalize_text`` is used
only for matching/searching/comparison. Existing rows keep the previously
stored canonical text and keep matching, since normalization is idempotent.
"""

from __future__ import annotations

import json

from books.db import BookRepository, Database
from books.models import Book
from books.normalization import normalize_text
from books.transfer import BookTransferService

TITLE = "کتاب آزمون ۱۲۳"
SUMMARY = "خط اول\nخط دوم"
AUTHOR = "نویسندهٔ نمونه"
PUBLISHER = "نشر ۱۲۳"


def test_model_preserves_user_typed_text_and_canonical_search_key():
    book = Book(
        title=TITLE,
        authors=(AUTHOR,),
        publisher=PUBLISHER,
        genres=("ژانر ۱",),
        subjects=("موضوع‌فرعی",),
        summary=SUMMARY,
    )
    assert book.title == TITLE
    assert book.summary == SUMMARY
    assert book.publisher == PUBLISHER
    assert book.search_title == "کتاب آزمون 123"
    assert normalize_text(book.summary) == "خط اول خط دوم"
    assert book.display_title == TITLE


def test_model_round_trip_is_idempotent():
    first = Book(title=TITLE, authors=(AUTHOR,), summary=SUMMARY)
    second = Book(
        title=first.title,
        original_title=first.original_title,
        authors=first.authors,
        translators=first.translators,
        publisher=first.publisher,
        language=first.language,
        genres=first.genres,
        subjects=first.subjects,
        summary=first.summary,
        notes=first.notes,
    )
    assert second == first


def test_repository_stores_display_text_while_search_stays_canonical(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(
        Book(
            title=TITLE,
            authors=(AUTHOR,),
            publisher=PUBLISHER,
            genres=("ژانر ۱",),
            summary=SUMMARY,
        )
    )

    row = repository.get(book_id)
    assert row["title"] == TITLE
    assert row["summary"] == SUMMARY
    assert row["publisher"] == PUBLISHER
    assert json.loads(row["authors_json"]) == [AUTHOR]

    # ASCII-digit / ZWNJ-variant queries still find the row.
    assert [row["id"] for row in repository.search("کتاب آزمون 123")] == [book_id]
    assert [row["id"] for row in repository.search(TITLE)] == [book_id]
    assert [row["id"] for row in repository.search("نویسندهٔ نمونه")] == [book_id]
    assert [row["id"] for row in repository.search("نویسنده نمونه")] == [book_id]


def test_duplicates_and_filters_match_across_digit_variants(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(
        Book(title=TITLE, authors=(AUTHOR,), genres=("ژانر ۱",))
    )

    ascii_variant = Book(title="کتاب آزمون 123", authors=(AUTHOR,))
    matches = repository.find_duplicates(ascii_variant)
    assert [row["id"] for row in matches] == [book_id]
    assert repository.find_duplicates(ascii_variant, exclude_id=book_id) == []

    assert [row["id"] for row in repository.filter_books(author="نویسندهٔ نمونه")] == [book_id]
    assert [row["id"] for row in repository.filter_books(genre="ژانر 1")] == [book_id]
    assert repository.filter_count(author="نویسندهٔ نمونه") == 1


def test_edit_save_round_trip_does_not_alter_user_text(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repository = BookRepository(db)
    book_id = repository.create_book(Book(title=TITLE, summary=SUMMARY))

    stored = repository.get(book_id)
    assert stored["title"] == TITLE
    assert repository.update_book(book_id, Book(title=TITLE, summary=SUMMARY)) is True
    reread = repository.get(book_id)
    assert reread["title"] == TITLE
    assert reread["summary"] == SUMMARY


def test_transfer_round_trip_preserves_display_text(tmp_path):
    source_db = Database(tmp_path / "source.sqlite3")
    source_db.migrate()
    source = BookRepository(source_db)
    source.create_book(Book(title=TITLE, authors=(AUTHOR,), summary=SUMMARY))

    payload = BookTransferService(source).export_json()
    assert "۱۲۳" in payload
    assert "خط اول\\nخط دوم" in payload

    target_db = Database(tmp_path / "target.sqlite3")
    target_db.migrate()
    target = BookTransferService(BookRepository(target_db))
    assert int(target.import_json(payload)) == 1

    row = BookRepository(target_db).list()[0]
    assert row["title"] == TITLE
    assert row["summary"] == SUMMARY
