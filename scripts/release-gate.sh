#!/usr/bin/env sh
set -eu

python -m pip install --upgrade pip build
rm -rf dist wheel-env
python -m build --sdist --wheel

test -f dist/*.tar.gz
test -f dist/*.whl

python -m venv wheel-env
wheel-env/bin/python -m pip install dist/*.whl
wheel-env/bin/python -m pip uninstall -y books >/dev/null
wheel-env/bin/python -m pip install dist/*.whl

test "$(wheel-env/bin/python -c 'import importlib.metadata as m; print(m.version("books"))')" = "1.0.0"
test "$(wheel-env/bin/python -c 'import books; print(books.__version__)')" = "1.0.0"

rm -f release-gate.sqlite3
BOOKS_DB_PATH="$PWD/release-gate.sqlite3" wheel-env/bin/python -c 'from books.config import load_settings; from books.db import Database; s=load_settings(); assert Database(s.db_path).migrate() == 11'
BOOKS_DB_PATH="$PWD/release-gate.sqlite3" wheel-env/bin/python -m books.health

BOOKS_DB_PATH="$PWD/release-gate.sqlite3" BOOKS_API_TOKEN="release-gate-token" wheel-env/bin/python -m books.runtime --host 127.0.0.1 --port 18080 >release-gate-runtime.log 2>&1 &
runtime_pid=$!
trap 'kill "$runtime_pid" 2>/dev/null || true; rm -f release-gate.sqlite3 release-gate-runtime.log' EXIT

python - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:18080"
headers = {"Authorization": "Bearer release-gate-token"}
for _ in range(50):
    try:
        with urllib.request.urlopen(base + "/health", timeout=1) as response:
            if response.status == 200:
                break
    except (OSError, urllib.error.URLError):
        time.sleep(0.2)
else:
    raise SystemExit("runtime did not become ready")

with urllib.request.urlopen(base + "/openapi.json", timeout=3) as response:
    payload = json.load(response)
assert payload["openapi"].startswith("3.")

request = urllib.request.Request(
    base + "/mcp",
    data=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "list_library", "arguments": {}},
    }).encode(),
    headers={"Content-Type": "application/json", **headers},
    method="POST",
)
with urllib.request.urlopen(request, timeout=3) as response:
    payload = json.load(response)
assert payload["jsonrpc"] == "2.0" and "result" in payload

change = {
    "id": "release-gate:book:1:1",
    "entity": "book",
    "entity_id": "1",
    "operation": "create",
    "version": 1,
    "payload": {"title": "release gate"},
    "changed_at": "2026-01-01T00:00:00+00:00",
}
request = urllib.request.Request(
    base + "/v1/sync/changes",
    data=json.dumps(change).encode(),
    headers={"Content-Type": "application/json", **headers},
    method="POST",
)
with urllib.request.urlopen(request, timeout=3) as response:
    payload = json.load(response)
assert payload["accepted"] is True and payload["applied"] is True

with urllib.request.urlopen(base + "/v1/sync/changes?since=0", timeout=3) as response:
    payload = json.load(response)
assert payload["changes"][0]["id"] == change["id"]
PY
