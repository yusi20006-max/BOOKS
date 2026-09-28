from __future__ import annotations

import argparse
import errno
import os
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PortOwner:
    pid: int
    command: str


class StartupError(RuntimeError):
    pass


def _run(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def _port_is_occupied(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                return True
            continue
        finally:
            sock.close()
    return False


def _proc_command(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as proc_file:
            return proc_file.read().replace(b"\0", b" ").decode().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return f"PID {pid}"


def _books_owner_from_process_list(port: int) -> PortOwner | None:
    output = _run(["ps", "-A", "-o", "pid=,args="])
    for line in output.splitlines():
        match = re.match(r"\s*(\d+)\s+(.*)", line)
        if not match:
            continue
        pid = int(match.group(1))
        command = match.group(2).strip()
        lowered = command.lower()
        port_arg = (
            f"--port {port}" in lowered
            or f"--port={port}" in lowered
            or f"--server.port {port}" in lowered
            or f"--server.port={port}" in lowered
        )
        books_command = (
            "books.runtime" in lowered
            or "books.startup" in lowered
            or ("streamlit" in lowered and "books" in lowered)
        )
        if books_command and port_arg:
            return PortOwner(pid, command)
    return None


def port_owner(port: int) -> PortOwner | None:
    output = _run(["fuser", "-n", "tcp", str(port)])
    pids = [int(x) for x in output.split() if x.isdigit()]
    if not pids:
        output = _run(["fuser", f"{port}/tcp"])
        pids = [int(x) for x in output.split() if x.isdigit()]
    if pids:
        pid = pids[0]
        return PortOwner(pid, _proc_command(pid))

    books_owner = _books_owner_from_process_list(port)
    if books_owner is not None:
        return books_owner

    if _port_is_occupied(port):
        return PortOwner(0, "unknown process (port is occupied; owner inspection unavailable)")

    return None


def is_books_process(owner: PortOwner) -> bool:
    command = owner.command.lower()
    return (
        "books.runtime" in command
        or "books.startup" in command
        or "src/books/app.py" in command
        or "streamlit" in command and "books" in command
    )


def wait_port_free(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_owner(port) is None:
            return True
        time.sleep(0.1)
    return port_owner(port) is None


def stop_books(owner: PortOwner, timeout: float = 5.0) -> None:
    if owner.pid <= 0:
        raise StartupError("BOOKS port owner PID is unavailable; refusing to stop an unknown process")
    try:
        os.kill(owner.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        raise StartupError(f"cannot stop BOOKS PID {owner.pid}: {exc}") from exc
    if wait_port_free(int(os.environ.get("BOOKS_PORT", "8080")), timeout):
        return
    raise StartupError(f"BOOKS PID {owner.pid} did not release the port within {timeout:.1f}s")


def build_runtime_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, "-m", "books.runtime", "--host", args.host, "--port", str(args.port), "--db", args.db]
    if args.token is not None:
        command += ["--token", args.token]
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BOOKS safe startup launcher")
    parser.add_argument("--host", default=os.getenv("BOOKS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BOOKS_PORT", "8080")))
    parser.add_argument("--db", default=os.getenv("BOOKS_DB_PATH", "books.sqlite3"))
    parser.add_argument("--token", default=os.getenv("BOOKS_API_TOKEN"))
    args = parser.parse_args(argv)

    owner = port_owner(args.port)
    if owner is not None:
        print(f"BOOKS startup: port {args.port} is occupied by PID {owner.pid}: {owner.command}", flush=True)
        if not is_books_process(owner):
            print("BOOKS startup: foreign process or unknown owner detected; refusing to stop it.", flush=True)
            return 2
        print(f"BOOKS startup: existing BOOKS process PID {owner.pid}; stopping safely.", flush=True)
        os.environ["BOOKS_PORT"] = str(args.port)
        stop_books(owner)

    if port_owner(args.port) is not None:
        raise StartupError(f"port {args.port} is still occupied after BOOKS stop")

    print(f"BOOKS startup: starting runtime on {args.host}:{args.port}", flush=True)
    os.execv(sys.executable, build_runtime_command(args))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StartupError as exc:
        print(f"BOOKS startup error: {exc}", file=sys.stderr)
        raise SystemExit(1)
