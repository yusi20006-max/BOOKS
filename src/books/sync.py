from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class ChangeType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class Change:
    id: str
    entity: str
    entity_id: str
    operation: ChangeType
    version: int
    payload: dict
    changed_at: str


@dataclass(frozen=True, slots=True)
class Conflict:
    entity: str
    entity_id: str
    local: Change
    remote: Change


def make_change(entity, entity_id, operation, payload, version=1):
    return Change(
        entity + ":" + entity_id + ":" + str(version),
        entity, entity_id, ChangeType(operation), version, payload,
        datetime.now(timezone.utc).isoformat(),
    )


def detect_conflict(local: Change, remote: Change) -> Conflict | None:
    if (
        local.entity == remote.entity
        and local.entity_id == remote.entity_id
        and local.version == remote.version
        and local.payload != remote.payload
    ):
        return Conflict(local.entity, local.entity_id, local, remote)
    return None


def resolve_conflict(conflict: Conflict, strategy: str) -> Change:
    if strategy not in {"local", "remote"}:
        raise ValueError("strategy must be local or remote")
    return conflict.local if strategy == "local" else conflict.remote


class SyncQueue:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._items: list[Change] = []
        if self.path:
            self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sync_queue "
                "(id TEXT PRIMARY KEY, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, "
                "next_attempt REAL NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0)"
            )

    def enqueue(self, change: Change) -> bool:
        if self.path:
            with sqlite3.connect(self.path) as conn:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO sync_queue(id,payload) VALUES(?,?)",
                    (change.id, json.dumps(change.__dict__ if hasattr(change, "__dict__") else {
                        "id": change.id, "entity": change.entity, "entity_id": change.entity_id,
                        "operation": change.operation.value, "version": change.version,
                        "payload": change.payload, "changed_at": change.changed_at,
                    }, ensure_ascii=False)),
                )
                return cursor.rowcount == 1
        self._items.append(change)
        return True

    def drain(self) -> list[Change]:
        if not self.path:
            items = list(self._items)
            self._items.clear()
            return items
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT payload FROM sync_queue WHERE completed=0 AND next_attempt<=? ORDER BY rowid",
                (time.time(),),
            ).fetchall()
            return [self._decode(row[0]) for row in rows]

    def mark_done(self, change_id: str) -> None:
        if self.path:
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE sync_queue SET completed=1 WHERE id=?", (change_id,))
        else:
            self._items = [item for item in self._items if item.id != change_id]

    def mark_failed(self, change_id: str, attempts: int, retry_after: float) -> None:
        if self.path:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "UPDATE sync_queue SET attempts=?,next_attempt=? WHERE id=?",
                    (attempts, time.time() + retry_after, change_id),
                )

    @staticmethod
    def _decode(raw: str) -> Change:
        value = json.loads(raw)
        return Change(value["id"], value["entity"], value["entity_id"],
                      ChangeType(value["operation"]), value["version"], value["payload"],
                      value["changed_at"])

    def pending_count(self) -> int:
        return len(self.drain()) if self.path else len(self._items)


class RemoteSyncClient:
    def __init__(self, endpoint: str, *, token: str | None = None, timeout: float = 5):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout

    def push(self, change: Change) -> dict:
        data = json.dumps({
            "id": change.id, "entity": change.entity, "entity_id": change.entity_id,
            "operation": change.operation.value, "version": change.version,
            "payload": change.payload, "changed_at": change.changed_at,
        }).encode()
        request = urllib.request.Request(
            self.endpoint + "/v1/sync/changes", data=data,
            headers={"Content-Type": "application/json",
                     **({"Authorization": "Bearer " + self.token} if self.token else {})},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.URLError as exc:
            raise ConnectionError("remote sync unavailable") from exc


def flush_queue(queue: SyncQueue, client: RemoteSyncClient, *, max_attempts: int = 5) -> int:
    completed = 0
    for change in queue.drain():
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            try:
                client.push(change)
                queue.mark_done(change.id)
                completed += 1
                break
            except ConnectionError:
                if attempts == max_attempts:
                    queue.mark_failed(change.id, attempts, min(60, 2 ** attempts))
                else:
                    time.sleep(min(0.1, 0.01 * 2 ** attempts))
    return completed


def sync_settings(local: dict, remote: dict) -> dict:
    return dict(remote) | {k: v for k, v in local.items() if k not in remote}
