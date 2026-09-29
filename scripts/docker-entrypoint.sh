#!/bin/sh
set -eu

# UI entrypoint (Streamlit, default 8501) vs API runtime (books.runtime/startup, default 8080).
# BOOKS_DB_PATH selects the SQLite file for both paths; Dockerfile defaults to /data/books.sqlite3.
# BOOKS_API_TOKEN is for the API runtime only and is intentionally not consumed here.

python -c 'from books.config import load_settings; from books.db import Database; s=load_settings(); Database(s.db_path).migrate()'
HOST="${BOOKS_HOST:-0.0.0.0}"
PORT="${BOOKS_PORT:-8501}"
if [ -f "src/books/app.py" ]; then
  APP="src/books/app.py"
else
  APP="$(python -c 'import books.app; print(books.app.__file__)')"
fi
exec streamlit run "$APP" --server.address "$HOST" --server.port "$PORT" --server.headless true
