from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupSchedule:
    interval_hours: int = 24

    def __post_init__(self):
        if isinstance(self.interval_hours, bool) or not isinstance(self.interval_hours, int) or self.interval_hours < 1:
            raise ValueError("interval must be a positive integer number of hours")

    def next_run(self, after: datetime) -> datetime:
        return after + timedelta(hours=self.interval_hours)


def encrypt_backup(data: bytes, password: str) -> bytes:
    if not password:
        raise ValueError("password is required")
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography is required for encrypted backups; install BOOKS with the [crypto] extra: pip install books[crypto]") from exc
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    return b"BOOKSENC1" + Fernet(key).encrypt(data)


def decrypt_backup(data: bytes, password: str) -> bytes:
    if not data.startswith(b"BOOKSENC1") or not password:
        raise ValueError("invalid encrypted backup")
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography is required for encrypted backups; install BOOKS with the [crypto] extra: pip install books[crypto]") from exc
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    return Fernet(key).decrypt(data[9:])


_BACKUP_LOCKS_GUARD = threading.Lock()
_BACKUP_LOCKS: dict[str, threading.Lock] = {}


class BackupAlreadyRunning(RuntimeError):
    """Raised when another scheduler instance is backing up the same destination."""


class BackupScheduler:
    def __init__(self, service, schedule: BackupSchedule, destination: str | Path, *, retention: int = 5):
        if isinstance(retention, bool) or not isinstance(retention, int) or retention < 1:
            raise ValueError("retention must be a positive integer")
        self.service = service
        self.schedule = schedule
        self.destination = Path(destination)
        self.retention = retention
        self.state_path = self.destination.with_suffix(self.destination.suffix + ".state")
        self._stop = threading.Event()
        self._thread = None
        self._run_lock = threading.Lock()
        self._start_lock = threading.Lock()
        lock_key = str(self.destination.resolve())
        with _BACKUP_LOCKS_GUARD:
            self._destination_lock = _BACKUP_LOCKS.setdefault(lock_key, threading.Lock())

    def _atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def run_once(self) -> Path:
        # Serialize runs on one scheduler; reject overlap from another scheduler
        # targeting the same destination in this process.
        with self._run_lock:
            if not self._destination_lock.acquire(blocking=False):
                raise BackupAlreadyRunning(
                    f"backup already running for {self.destination}"
                )
            try:
                data = self.service.create_backup_bytes()
                stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
                archive = self.destination.with_name(
                    f"{self.destination.stem}-{stamp}{self.destination.suffix}"
                )
                self._atomic(archive, data)
                try:
                    self._atomic(self.destination, data)
                    self._atomic(
                        self.state_path,
                        json.dumps(
                            {"last_run": datetime.now().astimezone().isoformat(), "status": "ok"}
                        ).encode(),
                    )
                except Exception:
                    archive.unlink(missing_ok=True)
                    raise
                self._prune()
                return self.destination
            finally:
                self._destination_lock.release()

    def _prune(self) -> None:
        candidates = [
            path
            for path in self.destination.parent.glob(
                self.destination.stem + "-*" + self.destination.suffix
            )
            if path.is_file() and not path.is_symlink()
        ]
        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for old in candidates[self.retention:]:
            try:
                old.unlink(missing_ok=True)
            except OSError:
                # A pruning failure must not invalidate the backup that was
                # already written and validated successfully.
                continue

    def run_once_recovering(self) -> Path | None:
        try:
            return self.run_once()
        except BackupAlreadyRunning:
            # An overlapping scheduled/manual run is a skip, not a backup failure.
            return None
        except Exception as exc:  # noqa: BLE001 - scheduled worker must survive backend failures
            try:
                self._atomic(
                    self.state_path,
                    json.dumps({"status": "error", "error": str(exc)}).encode(),
                )
            except OSError:
                # Preserve the worker even when the destination is unavailable.
                pass
            return None

    def start(self):
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _seconds_until_next_run(self, now: datetime | None = None) -> float:
        interval = self.schedule.interval_hours * 3600
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            last_run = state.get("last_run")
            if not isinstance(last_run, str):
                return float(interval)
            previous = datetime.fromisoformat(last_run)
            current = now or datetime.now().astimezone()
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=current.tzinfo)
            return max(0.0, interval - (current - previous).total_seconds())
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return float(interval)

    def _loop(self):
        while not self._stop.wait(self._seconds_until_next_run()):
            self.run_once_recovering()
