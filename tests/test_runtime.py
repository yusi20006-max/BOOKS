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
    connection.request(method, path, body=json.dumps(body) if body else None, headers=headers)
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
        assert status == 200 and spec["openapi"] == "3.0.3"
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
    finally:
        server.shutdown()
        thread.join(timeout=3)
