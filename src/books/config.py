from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int
    request_timeout_seconds: float
    user_agent: str
    google_books_api_key: str | None
    open_library_base_url: str


def load_settings(env_file: str | Path | None = None) -> Settings:
    if env_file is not None:
        load_dotenv(Path(env_file), override=False)
    else:
        load_dotenv(override=False)

    db_path = Path(os.getenv("BOOKS_DB_PATH", "data/books.sqlite3"))
    host = os.getenv("BOOKS_HOST", "127.0.0.1")
    port = _positive_int("BOOKS_PORT", 8501)
    timeout = _positive_float("BOOKS_REQUEST_TIMEOUT_SECONDS", 10.0)
    user_agent = os.getenv(
        "BOOKS_USER_AGENT",
        "BOOKS/0.1 (+https://github.com/yusi20006-max/BOOKS)",
    ).strip()
    if not user_agent:
        raise ValueError("BOOKS_USER_AGENT must not be empty")

    return Settings(
        db_path=db_path,
        host=host,
        port=port,
        request_timeout_seconds=timeout,
        user_agent=user_agent,
        google_books_api_key=os.getenv("GOOGLE_BOOKS_API_KEY") or None,
        open_library_base_url=os.getenv(
            "OPEN_LIBRARY_BASE_URL",
            "https://openlibrary.org",
        ).rstrip("/"),
    )


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
