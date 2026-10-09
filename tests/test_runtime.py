import json
import threading
from http.client import HTTPConnection

from books.runtime import create_server


def start_server(tmp_path):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def request(server, method, path, body=None, token="secret"):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return response.status, payload


def test_rest_and_mcp_runtime(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, health = request(server, "GET", "/health")
        assert status == 200 and health["status"] == "ok"
        status, spec = request(server, "GET", "/openapi.json")
        assert status == 200
        assert spec["openapi"] == "3.0.3"
        assert "/mcp" not in spec["paths"]  # MCP uses JSON-RPC, not REST OpenAPI paths.
        status, books = request(server, "GET", "/v1/books")
        assert status == 200 and books == []
        status, result = request(
            server, "POST", "/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "list_library", "arguments": {}}},
        )
        assert status == 200 and result["result"] == []
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_auth_is_enforced(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, _ = request(server, "GET", "/v1/books", token="wrong")
        assert status == 401
        status, _ = request(server, "POST", "/mcp", {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "list_library", "arguments": {}},
        }, token="wrong")
        assert status == 401
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_mcp_protocol_errors(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, payload = request(server, "POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "nope"})
        assert status == 200
        assert payload["error"]["code"] == -32600
        status, payload = request(server, "POST", "/mcp", {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "missing"}
        })
        assert status == 200
        assert payload["error"]["code"] == -32601
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_rate_limit_and_pagination_validation(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, payload = request(server, "GET", "/v1/books?limit=0")
        assert status == 400 and "limit" in payload["error"]
        status, payload = request(server, "GET", "/v1/books?limit=101")
        assert status == 400 and "limit" in payload["error"]
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_mcp_search_notes_is_serializable(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, payload = request(
            server, "POST", "/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "search_notes", "arguments": {"query": "test"}}},
        )
        assert status == 200
        assert payload["jsonrpc"] == "2.0"
        assert isinstance(payload.get("result"), list)
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_mcp_non_dict_request_returns_invalid(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, payload = request(server, "POST", "/mcp", ["not", "a", "dict"])
        assert status == 200
        assert payload["error"]["code"] == -32600
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_search_offset_is_honored(tmp_path):
    from books.db import BookRepository, Database

    db = Database(str(tmp_path / "books.sqlite3"))
    db.migrate()
    repo = BookRepository(db)
    repo.create({"id": "s1", "title": "offset book alpha"})
    repo.create({"id": "s2", "title": "offset book beta"})
    server, thread = start_server(tmp_path)
    try:
        status, first = request(server, "GET", "/v1/search?q=offset&limit=1&offset=0")
        assert status == 200 and len(first) == 1
        status, second = request(server, "GET", "/v1/search?q=offset&limit=1&offset=1")
        assert status == 200 and len(second) == 1
        assert first[0]["id"] != second[0]["id"]
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_mcp_backend_error_maps_to_internal(tmp_path):
    from books.runtime import Runtime

    class FailingRepo:
        db = None

        def search(self, *args, **kwargs):
            raise RuntimeError("boom")

        def list(self, *args, **kwargs):
            raise RuntimeError("boom")

        def get(self, *args, **kwargs):
            raise RuntimeError("boom")

        def reading_statistics(self, *args, **kwargs):
            raise RuntimeError("boom")

        def delete(self, *args, **kwargs):
            raise RuntimeError("boom")

    runtime = Runtime(FailingRepo(), token=None)
    payload = runtime.mcp_call(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "list_library", "arguments": {}}},
        client_id="test",
    )
    assert payload["error"]["code"] == -32603


def test_health_deep_check_validates_schema(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, health = request(server, "GET", "/health?deep=1")
        assert status == 200 and health == {"status": "ok", "mode": "deep"}
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_health_liveness_stays_cheap_without_db_touch(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        status, health = request(server, "GET", "/health")
        assert status == 200 and health == {"status": "ok"}
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_health_deep_reports_truncated_database(tmp_path):
    import sqlite3
    from http.server import ThreadingHTTPServer

    from books.db import BookRepository, Database
    from books.runtime import Runtime, make_handler

    db_path = tmp_path / "truncated.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE books (id TEXT PRIMARY KEY, title TEXT)")
    conn.commit()
    conn.close()

    db = Database(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Runtime(BookRepository(db), database=db)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, payload = request(server, "GET", "/health?deep=1")
        assert status == 503
        assert payload["status"] == "degraded"
        assert "reading_sessions" in payload["missing"]
        status, payload = request(server, "GET", "/health")
        assert status == 200 and payload == {"status": "ok"}
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_mcp_search_notes_returns_note_fields_over_http(tmp_path):
    from books.db import BookRepository, Database
    from books.models import Book

    db = Database(str(tmp_path / "books.sqlite3"))
    db.migrate()
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="کتاب آزمون", authors=("نویسنده",)))
    repo.add_note("note-http", book_id, "یادداشت آزمون از طریق HTTP", page=7)

    server, thread = start_server(tmp_path)
    try:
        status, payload = request(
            server, "POST", "/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "search_notes", "arguments": {"query": "آزمون"}}},
        )
        assert status == 200
        rows = payload["result"]
        assert rows and all("title" not in row for row in rows)
        note = next(row for row in rows if row["kind"] == "note")
        assert note["id"] == "note-http"
        assert note["page"] == 7
        assert note["book_id"] == book_id

        # Unknown argument shape maps to JSON-RPC invalid params, not a crash.
        status, payload = request(
            server, "POST", "/mcp",
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "search_notes", "arguments": {"unexpected": "x"}}},
        )
        assert status == 200
        assert payload["error"]["code"] == -32602
    finally:
        server.shutdown()
        thread.join(timeout=3)
