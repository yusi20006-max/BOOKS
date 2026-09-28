from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .api import APIError, BooksAPI
from .db import BookRepository, Database
from .mcp import build_server


class Runtime:
    def __init__(self, repository: BookRepository, *, token: str | None = None):
        self.api = BooksAPI(repository, token=token)
        self.mcp = build_server(repository)

    def mcp_call(self, request: dict, *, client_id: str) -> dict:
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or request.get("method") != "tools/call":
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "invalid request"}}
        params = request.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "invalid params"}}
        self.api.check_rate_limit(client_id)
        try:
            result = self.mcp.call(
                params["name"],
                params.get("arguments"),
                confirmed=bool(params.get("confirmed")),
                actor=client_id,
            )
        except KeyError:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}}
        except PermissionError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": str(exc)}}
        except (TypeError, ValueError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_handler(runtime: Runtime):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BOOKS/1.0"

        def _write(self, status: int, payload: object) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _token(self) -> str | None:
            value = self.headers.get("Authorization", "")
            return value[7:] if value.startswith("Bearer ") else None

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/health":
                self._write(200, {"status": "ok"})
                return
            if parsed.path == "/openapi.json":
                self._write(200, runtime.api.openapi())
                return
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            try:
                result = runtime.api.request(
                    "GET", parsed.path, token=self._token(), query=query,
                    client_id=self.client_address[0],
                )
                self._write(200, result)
            except APIError as exc:
                self._write(exc.status, {"error": exc.message})
            except (TypeError, ValueError):
                self._write(400, {"error": "invalid request"})

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 1_048_576:
                    self._write(413, {"error": "request body too large"})
                    return
                request = json.loads(self.rfile.read(length))
                token = self._token()
                runtime.api.authorize(token)
                if self.path == "/mcp":
                    try:
                        self._write(200, runtime.mcp_call(request, client_id=self.client_address[0]))
                    except APIError as exc:
                        self._write(exc.status, {"error": exc.message})
                    return
                if self.path == "/v1/sync/changes":
                    if not isinstance(request, dict) or not request.get("id"):
                        self._write(400, {"error": "change id is required"})
                        return
                    runtime.api.check_rate_limit(self.client_address[0])
                    self._write(200, {"accepted": True, "id": request["id"]})
                    return
                self._write(404, {"error": "endpoint not found"})
            except APIError as exc:
                self._write(exc.status, {"error": exc.message})
            except (json.JSONDecodeError, TypeError, ValueError):
                self._write(400, {"error": "invalid JSON request"})

        def log_message(self, *_args: object) -> None:
            return

    return Handler


def create_server(host: str, port: int, db_path: str, *, token: str | None = None):
    database = Database(db_path)
    database.migrate()
    return ThreadingHTTPServer(
        (host, port),
        make_handler(Runtime(BookRepository(database), token=token)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="BOOKS HTTP and MCP runtime")
    parser.add_argument("--host", default=os.getenv("BOOKS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BOOKS_PORT", "8080")))
    parser.add_argument("--db", default=os.getenv("BOOKS_DB_PATH", "books.sqlite3"))
    parser.add_argument("--token", default=os.getenv("BOOKS_API_TOKEN"))
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.db, token=args.token)
    print(f"BOOKS runtime listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
