from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int


def load_settings() -> Settings:
    db_path = Path(os.getenv("BOOKS_DB_PATH", "data/books.sqlite3"))
    host = os.getenv("BOOKS_HOST", "127.0.0.1")
    port = int(os.getenv("BOOKS_PORT", "8501"))
    return Settings(db_path=db_path, host=host, port=port)
