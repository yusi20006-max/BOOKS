from books.config import load_settings


def test_package_version():
    import books
    assert books.__version__ == "0.1.0"


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("BOOKS_DB_PATH", raising=False)
    monkeypatch.delenv("BOOKS_HOST", raising=False)
    monkeypatch.delenv("BOOKS_PORT", raising=False)

    settings = load_settings()

    assert str(settings.db_path) == "data/books.sqlite3"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8501
