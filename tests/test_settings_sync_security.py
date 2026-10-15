import json
import socket
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from books.db import Database
from books.runtime import create_server
from books.settings_sync import SettingsSyncRuntime


@pytest.mark.parametrize(
    "key",
    [
        "access_key",
        "provider.authorization",
        "bearer_token",
        "cookie_value",
        "session_id",
        "client-secret",
        "private_key",
    ],
)
def test_settings_sync_rejects_additional_credential_like_keys(tmp_path, key):
    runtime = SettingsSyncRuntime(Database(tmp_path / "settings.sqlite3"))
    with pytest.raises(ValueError, match="secret-bearing"):
        runtime.apply(device_id="phone", key=key, value="must-not-sync", base_version=0)
    assert runtime.changes_since(0)["revision"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"device_id": "phone", "key": "theme", "value": float("nan"), "base_version": 0},
        {"device_id": "phone", "key": "theme", "value": "x" * 4097, "base_version": 0},
        {"device_id": "phone", "key": "theme", "value": ["not", "scalar"], "base_version": 0},
        {"device_id": "phone", "key": "theme", "value": "dark", "base_version": True},
    ],
)
def test_settings_sync_rejects_hostile_values_without_persisting(tmp_path, payload):
    runtime = SettingsSyncRuntime(Database(tmp_path / "settings.sqlite3"))
    with pytest.raises((ValueError, TypeError)):
        runtime.apply(**payload)
    assert runtime.changes_since(0)["revision"] == 0


def test_settings_sync_http_rejects_unauthenticated_write_and_does_not_mutate(tmp_path):
    db_path = tmp_path / "books.sqlite3"
    server = create_server("127.0.0.1", 0, str(db_path), token="a-long-test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/sync/settings",
            data=json.dumps({
                "device_id": "phone",
                "key": "theme",
                "value": "dark",
                "base_version": 0,
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(request)
        assert exc.value.code == 401
        assert SettingsSyncRuntime(Database(db_path)).changes_since(0)["revision"] == 0
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_settings_sync_http_rejects_oversized_request_body(tmp_path):
    server = create_server(
        "127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="a-long-test-token"
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=5) as client:
            client.sendall(
                b"POST /v1/sync/settings HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Authorization: Bearer a-long-test-token\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 1048577\r\n"
                b"Connection: close\r\n\r\n"
            )
            response = client.recv(4096)
        assert b" 413 " in response.split(b"\r\n", 1)[0]
    finally:
        server.shutdown()
        thread.join(timeout=3)
