# BOOKS

Persian-first, offline-first personal library.

## Runtime API

Run `python -m books.runtime --host 127.0.0.1 --port 8080 --db books.sqlite3`. Configure `BOOKS_HOST`, `BOOKS_PORT`, `BOOKS_DB_PATH`, and optional `BOOKS_API_TOKEN`. REST is exposed under `/v1`, OpenAPI at `/openapi.json`, and MCP JSON-RPC 2.0 at `POST /mcp`. The Streamlit UI remains the user-facing application.
