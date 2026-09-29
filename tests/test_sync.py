from pathlib import Path

from books.db import Database
from books.sync import SyncRuntime, SyncQueue, detect_conflict, make_change, resolve_conflict, sync_settings


def test_change_and_conflict():
    a = make_change("book", "1", "update", {"title": "الف"}, 2)
    b = make_change("book", "1", "update", {"title": "ب"}, 2)
    c = detect_conflict(a, b)
    assert c and resolve_conflict(c, "local") is a


def test_queue_and_settings():
    q = SyncQueue()
    x = make_change("book", "1", "create", {})
    q.enqueue(x)
    assert q.drain() == [x] and q.drain() == []
    assert sync_settings({"rtl": True}, {"theme": "dark"}) == {"theme": "dark", "rtl": True}


def _runtime(tmp_path: Path) -> SyncRuntime:
    db = Database(tmp_path / "sync.sqlite3")
    db.migrate()
    return SyncRuntime(db)


def test_upsert_creates_missing_book(tmp_path):
    runtime = _runtime(tmp_path)
    change = make_change("book", "upsert-new", "upsert", {"title": "کتاب جدید"})

    assert runtime.apply(change) is True
    book = runtime.repo.get("upsert-new")
    assert book is not None
    assert book["title"] == "کتاب جدید"
    assert [item.id for item in runtime.changes_since()] == [change.id]


def test_upsert_updates_existing_book(tmp_path):
    runtime = _runtime(tmp_path)
    create = make_change("book", "upsert-existing", "create", {"title": "نسخه اول"})
    update = make_change("book", "upsert-existing", "upsert", {"title": "نسخه دوم"}, 2)

    assert runtime.apply(create) is True
    assert runtime.apply(update) is True
    assert runtime.repo.get("upsert-existing")["title"] == "نسخه دوم"
    assert [item.id for item in runtime.changes_since()] == [create.id, update.id]


def test_upsert_is_idempotent(tmp_path):
    runtime = _runtime(tmp_path)
    change = make_change("book", "upsert-idempotent", "upsert", {"title": "یک بار"})

    assert runtime.apply(change) is True
    assert runtime.apply(change) is False
    assert runtime.repo.get("upsert-idempotent")["title"] == "یک بار"
    assert len(runtime.changes_since()) == 1
