import pytest

from books.backup import BackupService
from books.db import BookRepository, Database
from books.models import Book


def test_backup_round_trip_is_valid_and_restore_is_atomic(tmp_path):
    source = tmp_path / "source.sqlite3"
    db = Database(source)
    db.migrate()
    repository = BookRepository(db)
    repository.create_book(Book(title="کتاب پشتیبان"))

    service = BackupService(source)
    payload = service.create_backup_bytes()
    assert payload[:16] == b"SQLite format 3\x00"

    target = tmp_path / "target.sqlite3"
    target_service = BackupService(target)
    target_service.restore_bytes(payload, overwrite=True)

    restored = BookRepository(Database(target))
    restored.db.migrate()
    assert restored.list()[0]["title"] == "کتاب پشتیبان"


def test_restore_requires_explicit_overwrite_and_validates_file(tmp_path):
    source = tmp_path / "source.sqlite3"
    Database(source).migrate()
    payload = BackupService(source).create_backup_bytes()

    target = tmp_path / "target.sqlite3"
    target_db = Database(target)
    target_db.migrate()

    service = BackupService(target)
    with pytest.raises(FileExistsError):
        service.restore_bytes(payload)

    with pytest.raises(ValueError):
        service.restore_bytes(b"not sqlite", overwrite=True)
