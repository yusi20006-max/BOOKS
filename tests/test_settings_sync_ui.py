from books.db import Database
from books.settings_sync_ui import (
    apply_remote_changes,
    load_sync_preferences,
    local_values,
    save_local_value,
    save_revision,
    save_sync_preferences,
)


def test_sync_ui_preferences_persist_locally_without_bearer_token(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    initial = load_sync_preferences(db)
    assert initial["endpoint"] == ""
    assert initial["enabled"] is False
    assert initial["device_id"].startswith("device-")

    saved = save_sync_preferences(
        db,
        endpoint="https://sync.example.test/",
        device_id="phone",
        enabled=True,
    )
    assert saved["endpoint"] == "https://sync.example.test"
    assert load_sync_preferences(db)["device_id"] == "phone"
    with db.connect() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(settings_sync_ui_preferences)")
        }
    assert "token" not in columns
    assert "bearer_token" not in columns


def test_sync_ui_requires_endpoint_when_enabled(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    load_sync_preferences(db)
    try:
        save_sync_preferences(db, endpoint="", device_id="phone", enabled=True)
    except ValueError as exc:
        assert "Endpoint and device ID" in str(exc)
    else:
        raise AssertionError("enabling sync without an endpoint must fail")


def test_pull_applies_only_newer_remote_values_and_tracks_revision(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    load_sync_preferences(db)
    save_local_value(db, key="theme", value="dark", version=2)

    applied = apply_remote_changes(
        db,
        [
            {"key": "theme", "value": "light", "version": 1},
            {"key": "font_size", "value": 16, "version": 3},
        ],
    )
    assert applied == 1
    assert local_values(db) == {
        "theme": {"value": "dark", "version": 2},
        "font_size": {"value": 16, "version": 3},
    }

    save_revision(db, 3)
    assert load_sync_preferences(db)["revision"] == 3


def test_local_sync_values_are_json_scalars(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    load_sync_preferences(db)
    save_local_value(db, key="theme", value=None, version=1)
    assert local_values(db)["theme"] == {"value": None, "version": 1}


def test_pull_never_applies_secret_bearing_keys(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    load_sync_preferences(db)
    applied = apply_remote_changes(
        db,
        [
            {"key": "api-key", "value": "do-not-store", "version": 1},
            {"key": "private_key", "value": "do-not-store", "version": 2},
            {"key": "theme", "value": "dark", "version": 3},
        ],
    )
    assert applied == 1
    assert local_values(db) == {"theme": {"value": "dark", "version": 3}}
