import json
import threading
from http.client import HTTPConnection

from books.db import BookRepository, Database
from books.models import Book
from books.runtime import create_server
from books.sync import Change, SyncRuntime


def test_clean_and_existing_database_e2e(tmp_path):
    path = tmp_path / "books.sqlite3"
    db = Database(path)
    assert db.migrate() == 11
    assert db.migrate() == 0
    repository = BookRepository(db)
    repository.create_book(Book(title="آزمون انتشار", authors=("نویسنده",)))

    server = create_server("127.0.0.1", 0, str(path), token="release-test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/v1/books", headers={"Authorization": "Bearer release-test"})
        response = connection.getresponse()
        books = json.loads(response.read())
        connection.close()
        assert response.status == 200
        assert books[0]["title"] == "آزمون انتشار"
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_sync_and_backup_roundtrip_e2e(tmp_path):
    path = tmp_path / "books.sqlite3"
    db = Database(path)
    assert db.migrate() == 11
    change = Change(
        "e2e:book:42:1", "book", "42", "create", 1,
        {"title": "E2E", "authors": ["Author"]}, "2026-01-01T00:00:00+00:00"
    )
    runtime = SyncRuntime(db)
    assert runtime.apply(change) is True
    assert runtime.apply(change) is False

    from books.backup import BackupService
    service = BackupService(path)
    backup = service.create_backup_bytes()
    restored = tmp_path / "restored.sqlite3"
    BackupService(restored).restore_bytes(backup)
    restored_db = Database(restored)
    assert restored_db.migrate() == 0
    restored_book = BookRepository(restored_db).get("42")
    assert restored_book["title"] == "E2E"
