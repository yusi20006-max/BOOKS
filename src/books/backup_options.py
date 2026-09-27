from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta


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
