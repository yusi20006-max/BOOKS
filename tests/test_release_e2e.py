import json
import threading
from http.client import HTTPConnection

from books.db import BookRepository, Database
from books.models import Book
from books.runtime import create_server


def test_clean_and_existing_database_e2e(tmp_path):
    path = tmp_path / "books.sqlite3"
    db = Database(path)
    assert db.migrate() == 7
    assert db.migrate() == 0
    repository = BookRepository(db)
    repository.create_book(Book(title="آزمون انتشار", authors=("نویسنده",)))

    server = create_server("127.0.0.1", 0, str(path), token="release-test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/v1/books", headers={"Authorization": "Bearer release-test"})
        response = connection.getresponse()
        books = json.loads(response.read())
        connection.close()
        assert response.status == 200
        assert books[0]["title"] == "آزمون انتشار"
    finally:
        server.shutdown()
        thread.join(timeout=3)
