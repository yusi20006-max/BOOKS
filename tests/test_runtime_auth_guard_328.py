"""Regression tests for Audit/P2 #328 non-loopback authentication guard."""

from __future__ import annotations

import contextlib
import io
import threading

import pytest

import books.runtime as runtime_mod
from books.runtime import _is_loopback_host, check_bind_auth, create_server


def test_loopback_hosts_are_recognized():
    for host in ("127.0.0.1", "127.3.4.5", "localhost", "::1", "[::1]", " LOCALHOST "):
        assert _is_loopback_host(host), host
    for host in ("0.0.0.0", "192.168.1.10", "::", "example.invalid"):
        assert not _is_loopback_host(host), host


def test_non_loopback_without_token_is_refused():
    for host in ("0.0.0.0", "192.168.1.10"):
        with pytest.raises(RuntimeError) as excinfo:
            check_bind_auth(host, None)
        message = str(excinfo.value)
        assert "BOOKS_API_TOKEN" in message
        assert "BOOKS_ALLOW_UNAUTHENTICATED" in message
        assert host in message


def test_loopback_and_token_pass_the_guard():
    check_bind_auth("127.0.0.1", None)  # unchanged loopback default
    check_bind_auth("localhost", None)
    check_bind_auth("0.0.0.0", "secret-token")  # token makes a routable bind safe


def test_opt_out_warns_but_allows():
    warnings: list[str] = []
    check_bind_auth("0.0.0.0", None, allow_unauthenticated=True, warn=warnings.append)
    assert len(warnings) == 1
    assert "WARNING" in warnings[0]
    assert "BOOKS_ALLOW_UNAUTHENTICATED" in warnings[0]


def _fake_server():
    class FakeServer:
        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            return None

    return FakeServer()


def test_main_refuses_non_loopback_without_token(monkeypatch, tmp_path):
    created: list[tuple] = []

    def refuse(*args, **kwargs):
        created.append(args)
        return _fake_server()

    monkeypatch.setattr(runtime_mod, "create_server", refuse)
    monkeypatch.delenv("BOOKS_ALLOW_UNAUTHENTICATED", raising=False)
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    # argparse reads sys.argv; drive main through a controlled argv.
    monkeypatch.setattr(
        "sys.argv",
        ["books.runtime", "--host", "0.0.0.0", "--port", "0", "--db", str(tmp_path / "b.sqlite3")],
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = runtime_mod.main()
    assert code == 2
    assert created == []  # never bound the port
    message = out.getvalue()
    assert "error" in message.lower()
    assert "BOOKS_API_TOKEN" in message
    assert "BOOKS_ALLOW_UNAUTHENTICATED" in message


def test_main_starts_with_token_on_non_loopback(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "create_server", lambda *a, **k: _fake_server())
    monkeypatch.delenv("BOOKS_ALLOW_UNAUTHENTICATED", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "books.runtime",
            "--host",
            "0.0.0.0",
            "--port",
            "0",
            "--db",
            str(tmp_path / "b.sqlite3"),
            "--token",
            "secret-token",
        ],
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = runtime_mod.main()
    assert code == 0
    assert "listening" in out.getvalue()


def test_main_starts_on_loopback_without_token(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "create_server", lambda *a, **k: _fake_server())
    monkeypatch.delenv("BOOKS_ALLOW_UNAUTHENTICATED", raising=False)
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["books.runtime", "--host", "127.0.0.1", "--port", "0", "--db", str(tmp_path / "b.sqlite3")],
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = runtime_mod.main()
    assert code == 0
    assert "listening" in out.getvalue()


def test_main_opt_out_starts_with_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "create_server", lambda *a, **k: _fake_server())
    monkeypatch.setenv("BOOKS_ALLOW_UNAUTHENTICATED", "1")
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["books.runtime", "--host", "0.0.0.0", "--port", "0", "--db", str(tmp_path / "b.sqlite3")],
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = runtime_mod.main()
    assert code == 0
    message = out.getvalue()
    assert "WARNING" in message
    assert "listening" in message


def test_configured_token_still_returns_401(tmp_path):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="secret-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import httpx

        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert httpx.get(base + "/health", timeout=5).status_code == 200
        assert httpx.get(base + "/v1/books", timeout=5).status_code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
