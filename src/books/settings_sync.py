from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .db import Database

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SECRET_PARTS = ("token", "secret", "password", "credential", "api_key", "apikey", "private_key")


class SettingsSyncRuntime:
    """Versioned, durable transport for non-secret user preferences across devices.

    Environment configuration and credentials are deliberately excluded. Each
    update carries the version observed by the writer; stale writes are rejected
    instead of silently overwriting another device's newer value.
    """

    def __init__(self, db: Database | None):
        self.db = db
        if self.db is None:
            return
        with self.db.connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS sync_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS sync_settings_changes (
                    version INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _validate_key(key: Any) -> str:
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError("setting key must be a lowercase identifier")
        # Hyphens are valid in setting names, so normalize separators before
        # checking credential markers (e.g. api-key and private-key).
        secret_check_key = key.lower().replace("-", "_")
        if any(part in secret_check_key for part in _SECRET_PARTS):
            raise ValueError("secret-bearing settings cannot be synchronized")
        return key

    @staticmethod
    def _encode_value(value: Any) -> str:
        if not (value is None or isinstance(value, (str, int, float, bool))):
            raise TypeError("setting value must be a JSON scalar")
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 4096:
            raise ValueError("setting value exceeds 4096 bytes")
        return encoded

    def changes_since(self, since: int = 0) -> dict[str, Any]:
        if self.db is None:
            raise RuntimeError("settings sync requires a database")
        if isinstance(since, bool) or not isinstance(since, int) or since < 0:
            raise ValueError("since must be a non-negative integer")
        with self.db.connect() as conn:
            # Keep the page and revision on one SQLite read snapshot. Without an
            # explicit transaction, a concurrent writer can commit between the
            # two SELECTs and advance the revision beyond the returned changes.
            conn.execute("BEGIN")
            rows = conn.execute(
                """SELECT version, device_id, key, value_json, updated_at
                   FROM sync_settings_changes WHERE version > ? ORDER BY version""",
                (since,),
            ).fetchall()
            current = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM sync_settings_changes"
            ).fetchone()[0]
            conn.commit()
        return {
            "revision": current,
            "changes": [
                {
                    "version": row["version"],
                    "device_id": row["device_id"],
                    "key": row["key"],
                    "value": json.loads(row["value_json"]),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ],
        }

    def apply(self, *, device_id: Any, key: Any, value: Any, base_version: Any) -> dict[str, Any]:
        if self.db is None:
            raise RuntimeError("settings sync requires a database")
        if not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 128:
            raise ValueError("device_id must be a non-empty string of at most 128 characters")
        key = self._validate_key(key)
        encoded = self._encode_value(value)
        if isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 0:
            raise ValueError("base_version must be a non-negative integer")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT value_json, version FROM sync_settings WHERE key = ?", (key,)
            ).fetchone()
            current_version = current["version"] if current else 0
            if current_version != base_version:
                if current is not None and current["value_json"] == encoded:
                    return {"accepted": True, "applied": False, "version": current_version}
                raise SettingsSyncConflict(key, current_version)
            if current is not None and current["value_json"] == encoded:
                return {"accepted": True, "applied": False, "version": current_version}
            cursor = conn.execute(
                """INSERT INTO sync_settings_changes(device_id, key, value_json, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (device_id.strip(), key, encoded, now),
            )
            version = cursor.lastrowid
            conn.execute(
                """INSERT INTO sync_settings(key, value_json, version, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     value_json=excluded.value_json,
                     version=excluded.version,
                     updated_at=excluded.updated_at""",
                (key, encoded, version, now),
            )
            return {"accepted": True, "applied": True, "version": version}


class SettingsSyncConflict(ValueError):
    def __init__(self, key: str, current_version: int):
        self.key = key
        self.current_version = current_version
        super().__init__(f"setting '{key}' changed remotely; current version is {current_version}")



class SettingsSyncClient:
    """HTTP client for pushing a preference and pulling the shared change log."""

    def __init__(self, endpoint: str, *, token: str | None = None, timeout: float = 5):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        request = Request(self.endpoint + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            details = json.loads(exc.read() or b"{}")
            if exc.code == 409:
                raise SettingsSyncConflict(
                    str(details.get("key", "")), int(details.get("current_version", 0))
                ) from exc
            if 400 <= exc.code < 500:
                raise ValueError(str(details.get("error", "settings sync request rejected"))) from exc
            raise ConnectionError("settings sync service unavailable") from exc
        except (URLError, TimeoutError) as exc:
            raise ConnectionError("settings sync service unavailable") from exc

    def push(self, *, device_id: str, key: str, value: Any, base_version: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/sync/settings",
            {"device_id": device_id, "key": key, "value": value, "base_version": base_version},
        )

    def pull(self, since: int = 0) -> dict[str, Any]:
        if isinstance(since, bool) or not isinstance(since, int) or since < 0:
            raise ValueError("since must be a non-negative integer")
        return self._request("GET", f"/v1/sync/settings?since={since}")
