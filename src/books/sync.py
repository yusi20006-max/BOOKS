from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import BookRepository, Database, transaction
from .models import Book
from .normalization import normalize_text


@dataclass(frozen=True, slots=True)
class Change:
    id: str
    entity: str
    entity_id: str
    operation: str
    version: int
    payload: dict[str, Any]
    changed_at: str


@dataclass(frozen=True, slots=True)
class Conflict:
    entity: str
    entity_id: str
    local: Change
    remote: Change


def make_change(entity, entity_id, operation, payload, version=1):
    return Change(
        f"{entity}:{entity_id}:{version}", entity, entity_id, str(operation), version,
        dict(payload), datetime.now(timezone.utc).isoformat(),
    )


def detect_conflict(local: Change, remote: Change) -> Conflict | None:
    if local.entity == remote.entity and local.entity_id == remote.entity_id and local.version == remote.version and local.payload != remote.payload:
        return Conflict(local.entity, local.entity_id, local, remote)
    return None


def resolve_conflict(conflict: Conflict, strategy: str) -> Change:
    if strategy not in {"local", "remote"}:
        raise ValueError("strategy must be local or remote")
    return conflict.local if strategy == "local" else conflict.remote


def _encode(change: Change) -> str:
    return json.dumps({
        "id": change.id, "entity": change.entity, "entity_id": change.entity_id,
        "operation": change.operation, "version": change.version,
        "payload": change.payload, "changed_at": change.changed_at,
    }, ensure_ascii=False)


class SyncQueue:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._items: list[Change] = []
        if self.path:
            self._initialize()

    def _initialize(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0)")

    def enqueue(self, change: Change) -> bool:
        if self.path:
            with sqlite3.connect(self.path) as conn:
                return conn.execute("INSERT OR IGNORE INTO sync_queue(id,payload) VALUES(?,?)", (change.id, _encode(change))).rowcount == 1
        if any(x.id == change.id for x in self._items):
            return False
        self._items.append(change)
        return True

    def drain(self) -> list[Change]:
        if not self.path:
            items, self._items = list(self._items), []
            return items
        with sqlite3.connect(self.path) as conn:
            rows=conn.execute("SELECT payload FROM sync_queue WHERE completed=0 AND next_attempt<=? ORDER BY rowid",(time.time(),)).fetchall()
        return [self._decode(x[0]) for x in rows]

    def mark_done(self, change_id):
        if self.path:
            with sqlite3.connect(self.path) as conn: conn.execute("UPDATE sync_queue SET completed=1 WHERE id=?", (change_id,))
        else:
            self._items=[x for x in self._items if x.id != change_id]

    def mark_failed(self, change_id, attempts, retry_after):
        if self.path:
            with sqlite3.connect(self.path) as conn: conn.execute("UPDATE sync_queue SET attempts=?,next_attempt=? WHERE id=?", (attempts,time.time()+retry_after,change_id))

    def pending_count(self):
        if not self.path: return len(self._items)
        with sqlite3.connect(self.path) as conn:
            return conn.execute("SELECT COUNT(*) FROM sync_queue WHERE completed=0 AND next_attempt<=?",(time.time(),)).fetchone()[0]

    @staticmethod
    def _decode(raw):
        value=json.loads(raw)
        return Change(value["id"],value["entity"],value["entity_id"],value["operation"],value["version"],value["payload"],value["changed_at"])


class RemoteSyncClient:
    def __init__(self, endpoint, *, token=None, timeout=5):
        self.endpoint=endpoint.rstrip("/")
        self.token=token
        self.timeout=timeout

    def push(self, change):
        data=_encode(change).encode()
        request=urllib.request.Request(self.endpoint+"/v1/sync/changes",data=data,headers={"Content-Type":"application/json",**({"Authorization":"Bearer "+self.token} if self.token else {})},method="POST")
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in {409,422}: raise ValueError("remote sync rejected change") from exc
            raise ConnectionError("remote sync unavailable") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ConnectionError("remote sync unavailable") from exc


def flush_queue(queue, client, *, max_attempts=5):
    if max_attempts < 1: raise ValueError("max_attempts must be positive")
    completed=0
    for change in queue.drain():
        attempts=0
        while attempts < max_attempts:
            attempts+=1
            try:
                client.push(change); queue.mark_done(change.id); completed+=1; break
            except ValueError:
                queue.mark_done(change.id)
                break
            except ConnectionError:
                if attempts == max_attempts: queue.mark_failed(change.id,attempts,min(60,2**attempts))
                else: time.sleep(min(0.1,0.01*2**attempts))
    return completed


class SyncRuntime:
    """Applies idempotent changes to a local repository and records the change log."""

    def __init__(self, db: Database):
        self.db=db
        self.repo=BookRepository(db)

    def apply(self, change: Change) -> bool:
        if change.entity != "book":
            raise ValueError("unsupported sync entity")
        with self.db.connect() as conn:
            existing=conn.execute("SELECT version FROM sync_changes WHERE id=?",(change.id,)).fetchone()
            if existing: return False
            current=conn.execute("SELECT * FROM books WHERE id=?",(change.entity_id,)).fetchone()
        if change.operation == "delete":
            self.repo.delete(change.entity_id)
        elif change.operation in {"create","update","upsert"}:
            payload=dict(change.payload); payload["id"]=change.entity_id
            if current:
                book=Book(
                    title=payload.get("title",""), original_title=payload.get("original_title"),
                    authors=payload.get("authors",[]), translators=payload.get("translators",[]),
                    publisher=payload.get("publisher"), pages=payload.get("pages"),
                    publication_year=payload.get("publication_year"), isbn10=payload.get("isbn10"),
                    isbn13=payload.get("isbn13"), language=payload.get("language"),
                    genres=payload.get("genres",[]), subjects=payload.get("subjects",[]),
                    summary=payload.get("summary"), cover_url=payload.get("cover_url"),
                    source_ids=payload.get("source_ids",{}), notes=payload.get("notes"),
                )
                self.repo.update_book(change.entity_id,book)
            else:
                book = Book(
                    title=payload.get("title", ""),
                    original_title=payload.get("original_title"),
                    authors=payload.get("authors", []),
                    translators=payload.get("translators", []),
                    publisher=payload.get("publisher"),
                    pages=payload.get("pages"),
                    publication_year=payload.get("publication_year"),
                    isbn10=payload.get("isbn10"),
                    isbn13=payload.get("isbn13"),
                    language=payload.get("language"),
                    genres=payload.get("genres", []),
                    subjects=payload.get("subjects", []),
                    summary=payload.get("summary"),
                    cover_url=payload.get("cover_url"),
                    source_ids=payload.get("source_ids", {}),
                    notes=payload.get("notes"),
                )
                self.repo.create_book(book, book_id=change.entity_id)
        else:
            raise ValueError("unsupported sync operation")
        with self.db.connect() as conn:
            conn.execute("INSERT INTO sync_changes(id,entity,entity_id,operation,version,payload_json,changed_at) VALUES(?,?,?,?,?,?,?)",(change.id,change.entity,change.entity_id,change.operation,change.version,json.dumps(change.payload,ensure_ascii=False),change.changed_at))
        return True

    def _apply_extended(self, book_id: str, payload: dict[str, Any]) -> None:
        """Apply sync-owned extended book state; omitted sections remain unchanged."""
        reading = payload.get("reading")
        personal = payload.get("personal")
        organization = payload.get("organization")
        if reading is None and personal is None and organization is None:
            return
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
                raise ValueError("book not found")
            if isinstance(reading, dict):
                allowed = {"unread", "reading", "finished", "abandoned"}
                status = reading.get("status")
                current_page = reading.get("current_page")
                progress = reading.get("progress")
                started_at = reading.get("started_at")
                finished_at = reading.get("finished_at")
                if status is not None and status not in allowed:
                    raise ValueError("invalid reading status")
                if current_page is not None and (not isinstance(current_page, int) or current_page < 0):
                    raise ValueError("invalid reading current page")
                if progress is not None and (not isinstance(progress, int) or not 0 <= progress <= 100):
                    raise ValueError("invalid reading progress")
                sets=[]; values=[]
                for column, value in (("reading_status", status), ("reading_current_page", current_page), ("reading_progress", progress), ("reading_started_at", started_at), ("reading_finished_at", finished_at)):
                    if column.replace("reading_", "") in reading:
                        sets.append(f"{column} = ?"); values.append(value)
                if sets:
                    sets.append("updated_at = ?"); values.append(datetime.now(timezone.utc).isoformat()); values.append(book_id)
                    conn.execute(f"UPDATE books SET {', '.join(sets)} WHERE id = ?", values)
            if isinstance(personal, dict):
                rating = personal.get("rating")
                if rating is not None and (not isinstance(rating, int) or not 1 <= rating <= 5):
                    raise ValueError("invalid personal rating")
                values = (book_id, rating, str(personal.get("note", "")).strip(), str(personal.get("quote", "")).strip(), int(bool(personal.get("favorite", False))), datetime.now(timezone.utc).isoformat())
                conn.execute("""INSERT INTO book_personal(book_id,rating,note,quote,favorite,updated_at) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(book_id) DO UPDATE SET rating=excluded.rating,note=excluded.note,quote=excluded.quote,favorite=excluded.favorite,updated_at=excluded.updated_at""", values)
            if isinstance(organization, dict):
                tags = tuple(dict.fromkeys(normalize_text(str(x)) for x in organization.get("tags", []) if normalize_text(str(x))))
                shelves = tuple(dict.fromkeys(normalize_text(str(x)) for x in organization.get("shelves", []) if normalize_text(str(x))))
                if "tags" in organization:
                    conn.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
                    for name in tags:
                        conn.execute("INSERT OR IGNORE INTO tags(id,name) VALUES (?,?)", (str(uuid.uuid4()), name))
                        row=conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
                        conn.execute("INSERT OR IGNORE INTO book_tags(book_id,tag_id) VALUES (?,?)", (book_id,row["id"]))
                if "shelves" in organization:
                    conn.execute("DELETE FROM book_shelves WHERE book_id = ?", (book_id,))
                    for name in shelves:
                        conn.execute("INSERT OR IGNORE INTO shelves(id,name) VALUES (?,?)", (str(uuid.uuid4()), name))
                        row=conn.execute("SELECT id FROM shelves WHERE name=?", (name,)).fetchone()
                        conn.execute("INSERT OR IGNORE INTO book_shelves(book_id,shelf_id) VALUES (?,?)", (book_id,row["id"]))

    def changes_since(self, version=0):
        with self.db.connect() as conn:
            rows=conn.execute("SELECT id,entity,entity_id,operation,version,payload_json,changed_at FROM sync_changes WHERE version>? ORDER BY version,id",(version,)).fetchall()
        return [Change(r["id"],r["entity"],r["entity_id"],r["operation"],r["version"],json.loads(r["payload_json"]),r["changed_at"]) for r in rows]


def sync_settings(local: dict, remote: dict) -> dict:
    return dict(remote) | {k:v for k,v in local.items() if k not in remote}
