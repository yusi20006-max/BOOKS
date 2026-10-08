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


def test_unknown_occupied_port_is_refused_without_kill(monkeypatch, capsys):
    monkeypatch.setattr(startup, "_run", lambda command: "")
    monkeypatch.setattr(startup, "_port_is_occupied", lambda port: True)
    killed = []
    monkeypatch.setattr(startup.os, "kill", lambda *args: killed.append(args))
    assert startup.main(["--port", "8080", "--db", "x.sqlite3"]) == 2
    assert killed == []
    assert "unknown process" in capsys.readouterr().out


def test_books_owner_is_stopped_and_runtime_execed(monkeypatch):
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    owner = startup.PortOwner(1234, "python -m books.runtime --port 8080")
    calls = []
    states = iter([owner, None, None])
    monkeypatch.setattr(startup, "port_owner", lambda port: next(states))
    monkeypatch.setattr(startup.os, "kill", lambda pid, sig: calls.append((pid, sig)))
    monkeypatch.setattr(startup.os, "execv", lambda executable, command: calls.append((executable, command)))
    assert startup.main(["--port", "8080", "--db", "x.sqlite3", "--token", "secret"]) == 0
    assert calls[0] == (1234, signal.SIGTERM)
    assert calls[1][0] == sys.executable
    assert calls[1][1][0:4] == [sys.executable, "-m", "books.runtime", "--host"]


def test_build_runtime_command_hides_token_from_argv():
    args = startup.argparse.Namespace(
        host="127.0.0.1", port=8080, db="x.sqlite3", token="super-secret-token-value",
    )
    command = startup.build_runtime_command(args)
    assert "--token" not in command
    assert "super-secret-token-value" not in " ".join(command)
    assert command[:4] == [startup.sys.executable, "-m", "books.runtime", "--host"]


def test_main_hands_token_via_environment_not_argv(monkeypatch):
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    monkeypatch.setattr(startup, "port_owner", lambda port: None)
    captured = []
    monkeypatch.setattr(startup.os, "execv", lambda executable, command: captured.append((executable, command)))
    assert startup.main(["--port", "8080", "--db", "x.sqlite3", "--token", "env-handed-token"]) == 0
    assert startup.os.environ["BOOKS_API_TOKEN"] == "env-handed-token"
    assert "--token" not in captured[0][1]
    assert "env-handed-token" not in " ".join(captured[0][1])


def test_main_without_token_leaves_environment_untouched(monkeypatch, capsys):
    monkeypatch.delenv("BOOKS_API_TOKEN", raising=False)
    monkeypatch.setattr(startup, "port_owner", lambda port: None)
    monkeypatch.setattr(startup.os, "execv", lambda executable, command: None)
    assert startup.main(["--port", "8080", "--db", "x.sqlite3"]) == 0
    assert "BOOKS_API_TOKEN" not in startup.os.environ
    assert "token" not in capsys.readouterr().out


def test_occupied_port_log_redacts_token(monkeypatch, capsys):
    owner = startup.PortOwner(1234, "python -m books.runtime --port 8080 --token leaked-secret-value")
    states = iter([owner, None, None])
    monkeypatch.setattr(startup, "port_owner", lambda port: next(states))
    monkeypatch.setattr(startup.os, "kill", lambda *args: None)
    monkeypatch.setattr(startup.os, "execv", lambda executable, command: None)
    assert startup.main(["--port", "8080", "--db", "x.sqlite3"]) == 0
    out = capsys.readouterr().out
    assert "leaked-secret-value" not in out
    assert "[REDACTED]" in out


def test_is_books_process():
    assert startup.is_books_process(startup.PortOwner(1, "python -m books.runtime"))
    assert startup.is_books_process(startup.PortOwner(1, "streamlit run src/books/app.py"))
    assert not startup.is_books_process(startup.PortOwner(1, "python -m other.app"))


def test_port_owner_reads_proc(monkeypatch):
    monkeypatch.setattr(startup.subprocess, "check_output", lambda *args, **kwargs: "1234\n")

    class FakeProcFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"python\0-m\0books.runtime\0"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: FakeProcFile())
    owner = startup.port_owner(8080)
    assert owner == startup.PortOwner(1234, "python -m books.runtime")


def test_termux_process_list_finds_books_owner(monkeypatch):
    monkeypatch.setattr(
        startup,
        "_run",
        lambda command: "4321 python -m books.runtime --port 8080\n",
    )
    owner = startup._books_owner_from_process_list(8080)
    assert owner == startup.PortOwner(4321, "python -m books.runtime --port 8080")


def test_books_owner_from_process_list_ignores_self(monkeypatch):
    current = startup.os.getpid()
    monkeypatch.setattr(
        startup,
        "_run",
        lambda command: f"{current} python -m books.startup --port 8080\n",
    )
    assert startup._books_owner_from_process_list(8080) is None


def test_port_owner_ignores_self_and_reports_unknown(monkeypatch):
    current = startup.os.getpid()
    monkeypatch.setattr(startup, "_port_is_occupied", lambda port: True)

    def fake_run(command):
        if "fuser" in command:
            return ""
        return f"{current} python -m books.startup --port 8080\n"

    monkeypatch.setattr(startup, "_run", fake_run)
    owner = startup.port_owner(8080)
    assert owner is not None
    assert owner.pid == 0
    assert not startup.is_books_process(owner)


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
