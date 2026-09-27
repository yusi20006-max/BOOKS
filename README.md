# BOOKS

Persian-first, offline-first personal library.

## Runtime API

Run `python -m books.runtime --host 127.0.0.1 --port 8080 --db books.sqlite3`. Configure `BOOKS_HOST`, `BOOKS_PORT`, `BOOKS_DB_PATH`, and optional `BOOKS_API_TOKEN`. REST is exposed under `/v1`, OpenAPI at `/openapi.json`, and MCP JSON-RPC 2.0 at `POST /mcp`. The Streamlit UI remains the user-facing application.

## Release policy

Version `1.0.0` is defined once in `src/books/__init__.py` and exposed to packaging through setuptools dynamic metadata. Core runtime dependencies are installed by the base package; optional integrations such as encrypted backup require their documented extra dependency and fail explicitly when unavailable.

A release is accepted only when clean-database migration, existing-database migration idempotency, REST/MCP runtime, offline smoke, full pytest, lint, and Docker build are green in CI. Release tags are created only from the verified main commit after that gate passes.
