from pathlib import Path

from books.db import Database
from books.sync import (
    SyncQueue,
    SyncRuntime,
    detect_conflict,
    make_change,
    resolve_conflict,
    sync_settings,
)


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



def test_upsert_preserves_structured_fields_on_create(tmp_path):
    runtime = _runtime(tmp_path)
    change = make_change(
        "book",
        "upsert-structured-create",
        "upsert",
        {
            "title": "Structured create",
            "authors": ["Author One", "Author Two"],
            "translators": ["Translator One"],
            "genres": ["fiction", "classic"],
            "subjects": ["identity", "memory"],
            "source_ids": {"isbn": "978-1-23456-789-0", "openlibrary": "OL123"},
        },
    )

    assert runtime.apply(change) is True
    book = runtime.repo.get("upsert-structured-create")
    assert book["authors_json"] == '["Author One", "Author Two"]'
    assert book["translators_json"] == '["Translator One"]'
    assert book["genres_json"] == '["fiction", "classic"]'
    assert book["subjects_json"] == '["identity", "memory"]'
    assert book["source_ids_json"] == '{"isbn": "978-1-23456-789-0", "openlibrary": "OL123"}'


def test_upsert_preserves_structured_fields_on_update(tmp_path):
    runtime = _runtime(tmp_path)
    create = make_change(
        "book",
        "upsert-structured-update",
        "create",
        {
            "title": "Structured update",
            "authors": ["Old Author"],
            "translators": ["Old Translator"],
            "genres": ["old"],
            "subjects": ["old subject"],
            "source_ids": {"source": "old"},
        },
    )
    update = make_change(
        "book",
        "upsert-structured-update",
        "upsert",
        {
            "title": "Structured update v2",
            "authors": ["New Author"],
            "translators": ["New Translator"],
            "genres": ["new"],
            "subjects": ["new subject"],
            "source_ids": {"source": "new", "other": "2"},
        },
        2,
    )

    assert runtime.apply(create) is True
    assert runtime.apply(update) is True
    book = runtime.repo.get("upsert-structured-update")
    assert book["authors_json"] == '["New Author"]'
    assert book["translators_json"] == '["New Translator"]'
    assert book["genres_json"] == '["new"]'
    assert book["subjects_json"] == '["new subject"]'
    assert book["source_ids_json"] == '{"source": "new", "other": "2"}'
