from __future__ import annotations

import json
import uuid
from typing import Any

from .db import Database


def load_sync_preferences(db: Database) -> dict[str, Any]:
    """Load only non-secret UI preferences; bearer tokens are never persisted."""
    with db.connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS settings_sync_ui_preferences (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                endpoint TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 0
            )"""
        )
        row = conn.execute(
            "SELECT endpoint, device_id, enabled, revision "
            "FROM settings_sync_ui_preferences WHERE id = 1"
        ).fetchone()
        if row is None:
            device_id = "device-" + uuid.uuid4().hex
            conn.execute(
                "INSERT INTO settings_sync_ui_preferences(id, endpoint, device_id, enabled, revision) "
                "VALUES (1, '', ?, 0, 0)",
                (device_id,),
            )
            return {"endpoint": "", "device_id": device_id, "enabled": False, "revision": 0}
    return {
        "endpoint": row["endpoint"],
        "device_id": row["device_id"],
        "enabled": bool(row["enabled"]),
        "revision": row["revision"],
    }


def save_sync_preferences(
    db: Database, *, endpoint: str, device_id: str, enabled: bool
) -> dict[str, Any]:
    endpoint = endpoint.strip().rstrip("/")
    device_id = device_id.strip()
    if endpoint and not endpoint.startswith(("http://", "https://")):
        raise ValueError("Endpoint must start with http:// or https://")
    if enabled and (not endpoint or not device_id):
        raise ValueError("Endpoint and device ID are required to enable sync")
    if not device_id or len(device_id) > 128:
        raise ValueError("Device ID must contain 1–128 characters")
    current = load_sync_preferences(db)
    with db.connect() as conn:
        conn.execute(
            """UPDATE settings_sync_ui_preferences
               SET endpoint = ?, device_id = ?, enabled = ? WHERE id = 1""",
            (endpoint, device_id, int(enabled)),
        )
    return {**current, "endpoint": endpoint, "device_id": device_id, "enabled": enabled}


def local_values(db: Database) -> dict[str, dict[str, Any]]:
    with db.connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS settings_sync_ui_values (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                version INTEGER NOT NULL
            )"""
        )
        rows = conn.execute("SELECT key, value_json, version FROM settings_sync_ui_values")
        return {
            row["key"]: {
                "value": json.loads(row["value_json"]),
                "version": row["version"],
            }
            for row in rows
        }


def save_local_value(db: Database, *, key: str, value: Any, version: int) -> None:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    with db.connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS settings_sync_ui_values (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                version INTEGER NOT NULL
            )"""
        )
        conn.execute(
            """INSERT INTO settings_sync_ui_values(key, value_json, version)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                 value_json=excluded.value_json, version=excluded.version""",
            (key, encoded, version),
        )


def apply_remote_changes(db: Database, changes: list[dict[str, Any]]) -> int:
    """Apply only newer remote revisions; return the number of local values changed."""
    current = local_values(db)
    applied = 0
    for change in changes:
        key = change.get("key")
        version = change.get("version")
        if not isinstance(key, str) or not isinstance(version, int):
            continue
        normalized = key.lower().replace("-", "").replace("_", "").replace(".", "")
        secret_parts = (
            "token", "secret", "password", "credential", "apikey", "privatekey",
            "accesskey", "authorization", "bearer", "cookie", "sessionid",
        )
        if any(part in normalized for part in secret_parts):
            continue
        if version <= current.get(key, {}).get("version", 0):
            continue
        save_local_value(db, key=key, value=change.get("value"), version=version)
        current[key] = {"value": change.get("value"), "version": version}
        applied += 1
    return applied


def save_revision(db: Database, revision: int) -> None:
    with db.connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS settings_sync_ui_preferences (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                endpoint TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 0
            )"""
        )
        conn.execute(
            "UPDATE settings_sync_ui_preferences SET revision = MAX(revision, ?) WHERE id = 1",
            (revision,),
        )
