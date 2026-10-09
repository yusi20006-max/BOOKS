#!/bin/sh
set -eu

# UI entrypoint (Streamlit, default 8501) vs API runtime (books.runtime/startup, default 8080).
# BOOKS_DB_PATH selects the SQLite file for both paths; Dockerfile defaults to /data/books.sqlite3.
# BOOKS_API_TOKEN is for the API runtime only and is intentionally not consumed here.

# Resolve the UI app file: prefer the packaged module path (works regardless of the
# working directory), then a source checkout, and fail loudly when neither exists.
# Resolution uses importlib.util.find_spec so no module code is executed here.
APP="$(python -c 'import importlib.util as u
try:
    spec = u.find_spec("books.app")
except Exception:
    spec = None
print(spec.origin if spec else "")')" || APP=""
if [ -z "$APP" ]; then
  if [ -f "src/books/app.py" ]; then
    APP="$(pwd)/src/books/app.py"
    export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
  else
    echo "ERROR: BOOKS UI entry point not found: the 'books' package is not importable and src/books/app.py is missing." >&2
    echo "ERROR: install the package (pip install .) or run this entrypoint from the repository root." >&2
    exit 1
  fi
fi

python -c 'from books.config import load_settings; from books.db import Database; s=load_settings(); Database(s.db_path).migrate()'
HOST="${BOOKS_HOST:-0.0.0.0}"
PORT="${BOOKS_PORT:-8501}"
exec streamlit run "$APP" --server.address "$HOST" --server.port "$PORT" --server.headless true
