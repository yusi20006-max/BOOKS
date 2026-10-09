"""Regression tests for Audit/P1 #321 UI entry points.

Covers the documented entry points (streamlit run script, python -m books.app,
the ``books`` console script, docker-entrypoint.sh) plus the absolute-import
requirement that makes them work.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP_SCRIPT = "from books.app import main\n\nmain()\n"


def test_app_py_has_no_relative_imports():
    """streamlit run executes app.py standalone, so relative imports abort it."""
    source = (REPO / "src" / "books" / "app.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*from\s+\.", source, re.MULTILINE)
    assert not re.search(r"^\s*import\s+\.", source, re.MULTILINE)


def test_console_script_targets_app_main():
    import tomllib

    data = tomllib.loads((REPO / "pyproject.toml").read_bytes().decode())
    assert data["project"]["scripts"]["books"] == "books.app:main"


def test_readme_documents_ui_start_commands():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for command in (
        "PYTHONPATH=src streamlit run src/books/app.py",
        "python -m books.app",
        "docker run",
    ):
        assert command in readme, command


def _entrypoint_env(tmp_path: Path, stub: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "BOOKS_DB_PATH": str(tmp_path / "entry.sqlite3"),
        # Some startup tests leak a BOOKS_PORT=8080 assignment into os.environ;
        # pin the documented default here so the assertion is deterministic.
        "BOOKS_PORT": "8501",
        "PYTHONPATH": str(REPO / "src"),
    }


def _run_entrypoint(cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(REPO / "scripts" / "docker-entrypoint.sh")],
        check=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_entrypoint_resolves_source_tree(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    streamlit_stub = stub / "streamlit"
    streamlit_stub.write_text('#!/bin/sh\necho "STREAMLIT-STUB $@"\nexit 0\n', encoding="utf-8")
    streamlit_stub.chmod(0o755)

    # Case A: run from the repository root (source tree present).
    case_a = _run_entrypoint(REPO, _entrypoint_env(tmp_path, stub))
    assert case_a.returncode == 0, case_a.stderr
    assert "STREAMLIT-STUB run" in case_a.stdout
    assert "books/app.py" in case_a.stdout
    assert "--server.address" in case_a.stdout
    assert "--server.port 8501" in case_a.stdout
    assert "--server.headless true" in case_a.stdout

    # Case B: installed-module layout (no ./src relative to cwd).
    case_b = _run_entrypoint(tmp_path, _entrypoint_env(tmp_path, stub))
    assert case_b.returncode == 0, case_b.stderr
    assert "STREAMLIT-STUB run" in case_b.stdout
    assert "books/app.py" in case_b.stdout


def test_entrypoint_fails_actionably_when_no_app_resolvable(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    fake_python = stub / "python"
    # Resolution probe reports "package not importable" (no output, exit 0);
    # the script must then fail before ever starting anything.
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
    }
    proc = _run_entrypoint(tmp_path, env)
    assert proc.returncode == 1
    assert "entry point not found" in proc.stderr


def test_module_help_runs_through_streamlit_cli():
    pytest.importorskip("streamlit")
    env = {
        **os.environ,
        "BOOKS_PORT": "8501",
        "PYTHONPATH": os.pathsep.join(
            part for part in (str(REPO / "src"), os.environ.get("PYTHONPATH")) if part
        ),
    }
    # ``python -m books.app --help`` must reach the Streamlit CLI and exit 0
    # instead of rendering in bare mode (the pre-fix behaviour exited 0 after
    # printing "missing ScriptRunContext" without ever starting a server).
    # Click's usage text on stdout is the discriminator: a bare-mode render
    # never emits it.
    proc = subprocess.run(
        [sys.executable, "-m", "books.app", "--help"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()


def test_console_script_runs_through_streamlit_cli():
    pytest.importorskip("streamlit")
    script = shutil.which("books")
    if script is None:
        pytest.skip("books console script not installed in this environment")
    proc = subprocess.run([script, "--help"], check=False, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "usage" in (proc.stdout + proc.stderr).lower()


def test_main_dispatches_to_launcher_outside_streamlit():
    pytest.importorskip("streamlit")
    from books import app

    launched: list[list[str]] = []
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app, "_inside_streamlit", lambda: False)
        patch.setattr(app, "launch", lambda: launched.append([]))
        app.main()
    assert len(launched) == 1


def test_launch_command_honours_book_port(monkeypatch):
    pytest.importorskip("streamlit")
    from books import app

    monkeypatch.delenv("BOOKS_PORT", raising=False)
    command = app._launch_command()
    assert command[1:4] == ["-m", "streamlit", "run"]
    assert command[4].endswith(os.path.join("books", "app.py"))
    assert "--server.port" not in command  # Streamlit default 8501

    monkeypatch.setenv("BOOKS_PORT", "8600")
    command = app._launch_command()
    assert command[command.index("--server.port") + 1] == "8600"

    # The launched command must remain recognisable to startup.is_books_process.
    from books.startup import PortOwner, is_books_process

    assert is_books_process(PortOwner(1, " ".join(app._launch_command())))


def test_app_renders_via_app_test(tmp_path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("BOOKS_DB_PATH", str(tmp_path / "appentry.sqlite3"))
        at = AppTest.from_string(APP_SCRIPT, default_timeout=30)
        at.run()
        assert not at.exception
