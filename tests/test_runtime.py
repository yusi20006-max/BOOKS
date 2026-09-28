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
