import signal
import socket
import subprocess
import sys
import time

from books import startup


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_foreign_owner_is_never_stopped(monkeypatch, capsys):
    owner = startup.PortOwner(1234, "python -m unrelated.service")
    killed = []
    monkeypatch.setattr(startup, "port_owner", lambda port: owner)
    monkeypatch.setattr(startup.os, "kill", lambda *args: killed.append(args))
    assert startup.main(["--port", "8080", "--db", "x.sqlite3"]) == 2
    assert killed == []
    assert "foreign process" in capsys.readouterr().out


def test_books_owner_is_stopped_and_runtime_execed(monkeypatch):
    owner = startup.PortOwner(1234, "python -m books.runtime --port 8080")
    calls = []
    states = iter([owner, None])
    monkeypatch.setattr(startup, "port_owner", lambda port: next(states))
    monkeypatch.setattr(startup.os, "kill", lambda pid, sig: calls.append((pid, sig)))
    monkeypatch.setattr(startup.os, "execv", lambda executable, command: calls.append((executable, command)))
    assert startup.main(["--port", "8080", "--db", "x.sqlite3", "--token", "secret"]) == 0
    assert calls[0] == (1234, signal.SIGTERM)
    assert calls[1][0] == sys.executable
    assert calls[1][1][0:4] == [sys.executable, "-m", "books.runtime", "--host"]


def test_is_books_process():
    assert startup.is_books_process(startup.PortOwner(1, "python -m books.runtime"))
    assert startup.is_books_process(startup.PortOwner(1, "streamlit run src/books/app.py"))
    assert not startup.is_books_process(startup.PortOwner(1, "python -m other.app"))


def test_port_owner_reads_proc(monkeypatch):
    monkeypatch.setattr(startup.subprocess, "check_output", lambda *args, **kwargs: "1234\n")
    monkeypatch.setattr(
        "builtins.open",
        lambda *args, **kwargs: type("F", (), {
            "read": lambda self: b"python\0-m\0books.runtime\0"
        })(),
    )
    owner = startup.port_owner(8080)
    assert owner == startup.PortOwner(1234, "python -m books.runtime")


def test_real_foreign_process_survives(tmp_path):
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"])
    try:
        time.sleep(0.3)
        result = subprocess.run(
            [sys.executable, "-m", "books.startup", "--port", str(port), "--db", str(tmp_path / "books.sqlite3")],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 2
        assert proc.poll() is None
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=3)
