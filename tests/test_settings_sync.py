import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from books.db import Database
from books.runtime import create_server
from books.settings_sync import SettingsSyncConflict, SettingsSyncRuntime


def test_settings_sync_is_versioned_and_persistent(tmp_path):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    first = SettingsSyncRuntime(db)
    result = first.apply(device_id="phone", key="theme", value="dark", base_version=0)
    assert result == {"accepted": True, "applied": True, "version": 1}
    assert first.changes_since(0)["changes"][0]["value"] == "dark"
    assert SettingsSyncRuntime(db).changes_since(0)["revision"] == 1


def test_settings_sync_rejects_stale_conflicting_writes(tmp_path):
    runtime = SettingsSyncRuntime(Database(tmp_path / "settings.sqlite3"))
    runtime.apply(device_id="phone", key="theme", value="dark", base_version=0)
    with pytest.raises(SettingsSyncConflict, match="changed remotely"):
        runtime.apply(device_id="tablet", key="theme", value="light", base_version=0)
    assert runtime.changes_since(0)["revision"] == 1


@pytest.mark.parametrize("key", ["api_key", "provider.password", "auth_token", "private_key", "api-key", "provider.private-key"])
def test_settings_sync_rejects_secrets(tmp_path, key):
    runtime = SettingsSyncRuntime(Database(tmp_path / "settings.sqlite3"))
    with pytest.raises(ValueError, match="secret-bearing"):
        runtime.apply(device_id="phone", key=key, value="never-sync-this", base_version=0)


def test_settings_sync_http_transport_requires_auth_and_supports_pull(tmp_path):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        data = json.dumps({
            "device_id": "phone", "key": "theme", "value": "dark", "base_version": 0
        }).encode()
        request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/sync/settings",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
            method="POST",
        )
        with urlopen(request) as response:
            assert json.loads(response.read())["applied"] is True
        request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/sync/settings?since=0",
            headers={"Authorization": "Bearer secret"},
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert body["changes"][0]["key"] == "theme"
        unauthenticated = Request(f"http://127.0.0.1:{server.server_port}/v1/sync/settings?since=0")
        with pytest.raises(HTTPError) as exc:
            urlopen(unauthenticated)
        assert exc.value.code == 401
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_settings_sync_client_push_pull_and_conflict(tmp_path):
    from books.settings_sync import SettingsSyncClient

    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = SettingsSyncClient(f"http://127.0.0.1:{server.server_port}", token="secret")
        assert client.push(device_id="phone", key="theme", value="dark", base_version=0)["applied"]
        pulled = client.pull()
        assert pulled["changes"][0]["key"] == "theme"
        assert pulled["changes"][0]["value"] == "dark"
        with pytest.raises(SettingsSyncConflict):
            client.push(device_id="tablet", key="theme", value="light", base_version=0)
    finally:
        server.shutdown()
        thread.join(timeout=3)



def test_settings_sync_http_rejects_missing_value_without_overwriting_null(tmp_path):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/sync/settings"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer secret"}
        initial = Request(
            endpoint,
            data=json.dumps({
                "device_id": "phone", "key": "theme", "value": "dark", "base_version": 0
            }).encode(),
            headers=headers,
            method="POST",
        )
        with urlopen(initial) as response:
            assert json.loads(response.read())["applied"] is True

        missing_value = Request(
            endpoint,
            data=json.dumps({
                "device_id": "phone", "key": "theme", "base_version": 1
            }).encode(),
            headers=headers,
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(missing_value)
        assert exc.value.code == 400

        pulled = Request(
            endpoint + "?since=0",
            headers={"Authorization": "Bearer secret"},
        )
        with urlopen(pulled) as response:
            body = json.loads(response.read())
        assert body["revision"] == 1
        assert body["changes"][0]["value"] == "dark"
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_settings_sync_changes_since_uses_one_read_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "settings.sqlite3"
    db = Database(db_path)
    db.migrate()
    with db.connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    runtime = SettingsSyncRuntime(db)
    runtime.apply(device_id="phone", key="theme", value="dark", base_version=0)

    original_connect = db.connect
    injected = False

    class ConnectionProxy:
        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *args):
            return self.conn.__exit__(*args)

        def execute(self, sql, params=()):
            nonlocal injected
            if "COALESCE(MAX(version), 0)" in sql and not injected:
                injected = True
                runtime.apply(device_id="tablet", key="font_size", value=16, base_version=0)
            return self.conn.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self.conn, name)

    monkeypatch.setattr(db, "connect", lambda: ConnectionProxy(original_connect()))
    snapshot = runtime.changes_since(0)
    assert injected
    assert [change["key"] for change in snapshot["changes"]] == ["theme"]
    assert snapshot["revision"] == snapshot["changes"][-1]["version"] == 1
    monkeypatch.setattr(db, "connect", original_connect)
    complete = runtime.changes_since(snapshot["revision"])
    assert complete["revision"] == 2
    assert [change["key"] for change in complete["changes"]] == ["font_size"]
