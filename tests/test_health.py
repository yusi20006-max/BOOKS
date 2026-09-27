from books.db import Database
from books.health import main


def test_health_check_accepts_initialized_database(tmp_path, monkeypatch):
    db_path = tmp_path / "books.sqlite3"
    Database(db_path).migrate()
    monkeypatch.setenv("BOOKS_DB_PATH", str(db_path))
    assert main() == 0
