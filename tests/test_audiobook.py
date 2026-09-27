from pathlib import Path

from books.db import BookRepository, Database
from books.models import Book


def test_audiobook_player_state_persists(tmp_path: Path):
    db = Database(tmp_path / "books.sqlite3")
    assert db.migrate() == 11
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="کتاب صوتی"), book_id="book-1")

    repo.add_audiobook(
        "audio-1",
        book_id,
        "/library/book.mp3",
        "mp3",
        3600,
    )
    repo.update_audiobook_progress("audio-1", position_seconds=120, speed=1.25)

    row = repo.get_audiobook("audio-1")
    assert row["book_id"] == book_id
    assert row["duration_seconds"] == 3600
    assert row["position_seconds"] == 120
    assert row["speed"] == 1.25


def test_audiobook_progress_is_bounded(tmp_path: Path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create_book(Book(title="کتاب صوتی"), book_id="book-1")
    repo.add_audiobook("audio-1", "book-1", "/library/book.mp3", "mp3", 100)

    try:
        repo.update_audiobook_progress("audio-1", position_seconds=101, speed=1.0)
    except ValueError as exc:
        assert str(exc) == "audio position exceeds duration"
    else:
        raise AssertionError("expected bounded audiobook progress")


def test_audiobook_list_is_book_scoped(tmp_path: Path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    repo.create_book(Book(title="اول"), book_id="book-1")
    repo.create_book(Book(title="دوم"), book_id="book-2")
    repo.add_audiobook("audio-1", "book-1", "/a.mp3", "mp3", 10)
    repo.add_audiobook("audio-2", "book-2", "/b.mp3", "mp3", 20)

    rows = repo.list_audiobooks("book-1")
    assert [row["id"] for row in rows] == ["audio-1"]
