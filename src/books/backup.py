from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .security import harden_file


class BackupService:
    """Create and restore validated SQLite backups atomically."""

    MAX_BACKUP_BYTES = 100 * 1024 * 1024

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def create_backup_bytes(self) -> bytes:
        if not self.database_path.exists():
            raise FileNotFoundError(self.database_path)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "books-backup.sqlite3"
            source = sqlite3.connect(self.database_path)
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            self._validate_file(target)
            data = target.read_bytes()
            if len(data) > self.MAX_BACKUP_BYTES:
                raise ValueError("backup exceeds maximum supported size")
            return data

    def backup_filename(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"books-backup-{stamp}.sqlite3"

    def restore_bytes(self, data: bytes, *, overwrite: bool = False) -> None:
        if not data:
            raise ValueError("backup is empty")
        if len(data) > self.MAX_BACKUP_BYTES:
            raise ValueError("backup exceeds maximum supported size")

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "restore.sqlite3"
            source.write_bytes(data)
            self._validate_file(source)

            if self.database_path.exists() and not overwrite:
                raise FileExistsError(
                    "database exists; explicit overwrite confirmation is required"
                )

            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            temp_destination = self.database_path.with_suffix(
                self.database_path.suffix + ".restore.tmp"
            )
            if temp_destination.exists():
                temp_destination.unlink()
            try:
                source_conn = sqlite3.connect(source)
                destination_conn = sqlite3.connect(temp_destination)
                try:
                    source_conn.backup(destination_conn)
                finally:
                    destination_conn.close()
                    source_conn.close()
                self._validate_file(temp_destination)
                os.replace(temp_destination, self.database_path)
                harden_file(str(self.database_path))
            finally:
                if temp_destination.exists():
                    temp_destination.unlink()

    @staticmethod
    def _validate_file(path: Path) -> None:
        conn = sqlite3.connect(path)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("SQLite integrity check failed")
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {"books", "schema_migrations"}
            if not required.issubset(tables):
                raise ValueError("backup is not a valid BOOKS database")
        except sqlite3.DatabaseError as exc:
            raise ValueError("invalid SQLite backup") from exc
        finally:
            conn.close()
