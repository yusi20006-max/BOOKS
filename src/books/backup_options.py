from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True,slots=True)
class BackupSchedule:
 interval_hours:int=24
 def __post_init__(self):
  if self.interval_hours<1: raise ValueError("interval must be positive")
 def next_run(self,after:datetime)->datetime: return after+timedelta(hours=self.interval_hours)

def encrypt_backup(data:bytes,password:str)->bytes:
 if not password: raise ValueError("password is required")
 try:
  from cryptography.fernet import Fernet
 except ImportError as exc: raise RuntimeError("cryptography is required") from exc
 key=base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
 return b"BOOKSENC1"+Fernet(key).encrypt(data)

def decrypt_backup(data:bytes,password:str)->bytes:
 if not data.startswith(b"BOOKSENC1") or not password: raise ValueError("invalid encrypted backup")
 from cryptography.fernet import Fernet
 key=base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
 return Fernet(key).decrypt(data[9:])



class BackupScheduler:
    """Execute periodic backups in a background thread with durable last-run state."""

    def __init__(self, service, schedule: BackupSchedule, destination: str | Path):
        import threading
        self.service = service
        self.schedule = schedule
        self.destination = Path(destination)
        self.state_path = self.destination.with_suffix(self.destination.suffix + ".state")
        self._stop = threading.Event()
        self._thread = None

    def run_once(self) -> Path:
        data = self.service.create_backup_bytes()
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temp = self.destination.with_suffix(self.destination.suffix + ".tmp")
        temp.write_bytes(data)
        temp.replace(self.destination)
        self.state_path.write_text(
            json.dumps({"last_run": datetime.now().astimezone().isoformat()}), encoding="utf-8"
        )
        return self.destination

    def start(self) -> None:
        import threading
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.wait(self.schedule.interval_hours * 3600):
            self.run_once()
