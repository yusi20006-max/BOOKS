from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .api import APIError, BooksAPI
from .backup import BackupService
from .backup_options import BackupSchedule, BackupScheduler
from .db import BookRepository, Database
from .health import missing_tables
from .mcp import build_server
from .sync import Change, SyncRuntime


class Runtime:
    def __init__(self, repository: BookRepository, *, token: str | None = None, database: Database | None = None):
        self.api=BooksAPI(repository,token=token)
        self.mcp=build_server(repository)
        self.sync=SyncRuntime(database or repository.db)

    def mcp_call(self, request: dict, *, client_id: str) -> dict:
        request_id=request.get("id") if isinstance(request, dict) else None
        if not isinstance(request, dict):
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32600,"message":"invalid request"}}
        if request.get("jsonrpc")!="2.0" or request.get("method")!="tools/call":
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32600,"message":"invalid request"}}
        params=request.get("params")
        if not isinstance(params,dict) or not isinstance(params.get("name"),str):
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32602,"message":"invalid params"}}
        self.api.check_rate_limit(client_id)
        try:
            result=self.mcp.call(params["name"],params.get("arguments"),confirmed=bool(params.get("confirmed")),actor=client_id)
        except KeyError:
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"method not found"}}
        except PermissionError as exc:
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32001,"message":str(exc)}}
        except (TypeError,ValueError) as exc:
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32602,"message":str(exc)}}
        except Exception:  # noqa: BLE001 - map backend failures to JSON-RPC internal error
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32603,"message":"internal error"}}
        return {"jsonrpc":"2.0","id":request_id,"result":result}


def make_handler(runtime: Runtime):
    class Handler(BaseHTTPRequestHandler):
        server_version="BOOKS/1.0"
        def _write(self,status,payload):
            data=json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
        def _token(self):
            value=self.headers.get("Authorization","")
            return value[7:] if value.startswith("Bearer ") else None
        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path=="/health":
                # Cheap liveness probe by default; `?deep=1` additionally
                # validates the full schema (readiness) without making the
                # base endpoint DB-heavy.
                query={k:v[-1] for k,v in parse_qs(parsed.query).items()}
                if query.get("deep") not in (None,"","0","false"):
                    try:
                        with runtime.api.repo.db.connect() as conn:
                            absent=sorted(missing_tables(conn))
                    except Exception:  # noqa: BLE001 - unreadable DB means not ready
                        self._write(503,{"status":"degraded","error":"database is not readable"}); return
                    if absent:
                        self._write(503,{"status":"degraded","missing":absent}); return
                    self._write(200,{"status":"ok","mode":"deep"}); return
                self._write(200,{"status":"ok"}); return
            if parsed.path=="/openapi.json": self._write(200,runtime.api.openapi()); return
            query={k:v[-1] for k,v in parse_qs(parsed.query).items()}
            if parsed.path=="/v1/sync/changes":
                try:
                    runtime.api.authorize(self._token()); runtime.api.check_rate_limit(self.client_address[0])
                    since=int(query.get("since","0"))
                    if since<0: raise ValueError
                    self._write(200,{"changes":[asdict(c) for c in runtime.sync.changes_since(since)]})
                except (ValueError,TypeError): self._write(400,{"error":"since must be a non-negative integer"})
                except APIError as exc: self._write(exc.status,{"error":exc.message})
                except Exception:  # noqa: BLE001 - never drop connection, return 500 JSON
                    self._write(500,{"error":"internal error"})
                return
            try:
                self._write(200,runtime.api.request("GET",parsed.path,token=self._token(),query=query,client_id=self.client_address[0]))
            except APIError as exc: self._write(exc.status,{"error":exc.message})
            except (TypeError,ValueError): self._write(400,{"error":"invalid request"})
            except Exception:  # noqa: BLE001 - never drop connection, return 500 JSON
                self._write(500,{"error":"internal error"})
        def do_POST(self):
            try:
                length=int(self.headers.get("Content-Length","0"))
                if length<0 or length>1_048_576: self._write(413,{"error":"request body too large"}); return
                request=json.loads(self.rfile.read(length))
                token=self._token(); runtime.api.authorize(token)
                if self.path=="/mcp":
                    try: self._write(200,runtime.mcp_call(request,client_id=self.client_address[0]))
                    except APIError as exc: self._write(exc.status,{"error":exc.message})
                    return
                if self.path=="/v1/sync/changes":
                    if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not request["id"]:
                        self._write(400, {"error": "change id is required"}); return
                    required={"entity","entity_id","operation","version","payload","changed_at"}
                    if not required.issubset(request):
                        self._write(400, {"error": "invalid change"}); return
                    if request["entity"] != "book":
                        self._write(400, {"error": "entity must be book"}); return
                    if not isinstance(request["entity_id"], str) or not request["entity_id"]:
                        self._write(400, {"error": "entity_id must be a non-empty string"}); return
                    if request["operation"] not in {"create", "update", "upsert", "delete"}:
                        self._write(400, {"error": "unsupported sync operation"}); return
                    if isinstance(request["version"], bool) or not isinstance(request["version"], int) or request["version"] < 1:
                        self._write(400, {"error": "version must be a positive integer"}); return
                    if not isinstance(request["payload"], dict):
                        self._write(400, {"error": "payload must be an object"}); return
                    if not isinstance(request["changed_at"], str) or not request["changed_at"]:
                        self._write(400, {"error": "changed_at must be a non-empty string"}); return
                    runtime.api.check_rate_limit(self.client_address[0])
                    try:
                        change=Change(request["id"],request["entity"],request["entity_id"],request["operation"],request["version"],request["payload"],request["changed_at"])
                        applied=runtime.sync.apply(change)
                    except ValueError as exc:
                        self._write(400,{"error":str(exc)})
                        return
                    self._write(200,{"accepted":True,"id":change.id,"applied":applied})
                    return
                self._write(404,{"error":"endpoint not found"})
            except APIError as exc: self._write(exc.status,{"error":exc.message})
            except (json.JSONDecodeError,TypeError,ValueError): self._write(400,{"error":"invalid JSON request"})
            except Exception:  # noqa: BLE001 - never drop connection, return 500 JSON
                self._write(500,{"error":"internal error"})
        def log_message(self,*_args): return
    return Handler


def _is_loopback_host(host: str) -> bool:
    """True when the bind address only accepts local connections."""
    normalized = str(host).strip().lower()
    if normalized in {"localhost", "localhost.localdomain"}:
        return True
    if normalized.count(".") == 3 and normalized.startswith("127."):
        return True
    return normalized in {"::1", "[::1]"}


def check_bind_auth(host, token, *, allow_unauthenticated: bool = False, warn=print) -> None:
    """Refuse a non-loopback bind without a token unless explicitly opted out.

    The REST/MCP/sync surface is an open read/write API when no bearer token is
    configured, so binding it to a routable interface would expose the library
    to anyone who can reach the port. ``BOOKS_ALLOW_UNAUTHENTICATED=1`` is the
    documented, explicit opt-out and logs a warning when used.
    """
    if _is_loopback_host(host) or token:
        return
    if allow_unauthenticated:
        warn(
            f"BOOKS runtime: WARNING: binding {host} without an API token "
            "(BOOKS_ALLOW_UNAUTHENTICATED=1); the REST/MCP/sync API is open to "
            "anyone who can reach this port.",
        )
        return
    raise RuntimeError(
        f"refusing to bind non-loopback host {host!r} without an API token: "
        "set BOOKS_API_TOKEN (or --token), or explicitly opt out with "
        "BOOKS_ALLOW_UNAUTHENTICATED=1 (insecure), or bind 127.0.0.1"
    )


class BooksHTTPServer(ThreadingHTTPServer):
    """HTTP server that owns and stops its optional scheduled-backup worker."""

    backup_scheduler: BackupScheduler | None = None

    def server_close(self):
        if self.backup_scheduler is not None:
            self.backup_scheduler.stop()
        super().server_close()


def create_server(
    host, port, db_path, *, token=None, backup_path=None,
    backup_interval_hours=None, backup_retention=None,
):
    database = Database(db_path)
    database.migrate()
    server = BooksHTTPServer(
        (host, port),
        make_handler(Runtime(BookRepository(database), token=token, database=database)),
    )
    configured_path = backup_path if backup_path is not None else os.getenv("BOOKS_BACKUP_PATH", "").strip()
    if configured_path:
        try:
            interval = backup_interval_hours if backup_interval_hours is not None else int(
                os.getenv("BOOKS_BACKUP_INTERVAL_HOURS", "24")
            )
            retention = backup_retention if backup_retention is not None else int(
                os.getenv("BOOKS_BACKUP_RETENTION", "5")
            )
            scheduler = BackupScheduler(
                BackupService(db_path), BackupSchedule(interval), configured_path, retention=retention
            )
        except (TypeError, ValueError) as exc:
            server.server_close()
            raise ValueError(
                "invalid scheduled backup configuration; use BOOKS_BACKUP_INTERVAL_HOURS >= 1 "
                "and BOOKS_BACKUP_RETENTION >= 1"
            ) from exc
        server.backup_scheduler = scheduler
        scheduler.start()
    return server


def main():
    parser=argparse.ArgumentParser(description="BOOKS HTTP and MCP runtime")
    parser.add_argument("--host",default=os.getenv("BOOKS_HOST","127.0.0.1")); parser.add_argument("--port",type=int,default=int(os.getenv("BOOKS_PORT","8080"))); parser.add_argument("--db",default=os.getenv("BOOKS_DB_PATH","books.sqlite3")); parser.add_argument("--token",default=os.getenv("BOOKS_API_TOKEN"))
    args=parser.parse_args()
    allow_unauthenticated=os.getenv("BOOKS_ALLOW_UNAUTHENTICATED","").strip().lower() in {"1","true","yes","on"}
    try:
        check_bind_auth(args.host,args.token,allow_unauthenticated=allow_unauthenticated)
    except RuntimeError as exc:
        print(f"BOOKS runtime: error: {exc}",flush=True)
        return 2
    server=create_server(args.host,args.port,args.db,token=args.token)
    print(f"BOOKS runtime listening on http://{args.host}:{args.port}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: return 0
    finally: server.server_close()
    return 0


if __name__=="__main__": raise SystemExit(main())
