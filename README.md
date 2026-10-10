# BOOKS

Persian-first, offline-first personal library.

## Runtime API

Run `python -m books.runtime --host 127.0.0.1 --port 8080 --db books.sqlite3`. Configure `BOOKS_HOST`, `BOOKS_PORT`, `BOOKS_DB_PATH`, and optional `BOOKS_API_TOKEN`. REST is exposed under `/v1`, OpenAPI at `/openapi.json`, and MCP JSON-RPC 2.0 at `POST /mcp`. The Streamlit UI remains the user-facing application.

The runtime binds `127.0.0.1` by default and is loopback-only unless a token is configured. Binding a non-loopback `BOOKS_HOST` without `BOOKS_API_TOKEN` is refused with a non-zero exit and an actionable error. To intentionally expose an unauthenticated API on a routable interface, set the explicit opt-out `BOOKS_ALLOW_UNAUTHENTICATED=1`; the runtime then logs a startup warning.

`GET /health` is a cheap liveness probe that never touches the database. `GET /health?deep=1` is the documented readiness check: it validates the full database schema (derived from the migration sources) and returns `503` with the missing tables when the database is truncated or unreadable. The `python -m books.health` CLI and backup restore apply the same full validation and reject incomplete databases.

## UI (Streamlit)

The Streamlit UI is the user-facing application. Any of the following starts it (the server honours `BOOKS_PORT`, default `8501`):

- Installed package: `books`
- Module entry point: `python -m books.app`
- Source checkout without installing (Termux/proot included): from the repository root, run `PYTHONPATH=src streamlit run src/books/app.py`
- Docker: the image entrypoint starts the UI automatically, e.g. `docker run --rm -p 8501:8501 books` (it resolves the packaged module and exits non-zero with an actionable error if no app file can be resolved)

## AI assistant configuration

The «دستیار هوشمند» page reads its gateways from the environment. The local gateway defaults to `BOOKS_AI_BASE_URL=http://127.0.0.1:8000/v1` with `BOOKS_AI_MODEL` and optional `BOOKS_AI_API_KEY`. Setting `BOOKS_AI_FALLBACK_BASE_URL` enables a second gateway (`BOOKS_AI_FALLBACK_MODEL`, `BOOKS_AI_FALLBACK_API_KEY`) used when the local one fails. Every supported variable is listed with placeholder values in `.env.example`.

## Sync contract

The runtime sync endpoint accepts book changes using `create`, `update`, `upsert`, and `delete` operations. `upsert` creates the book when `entity_id` does not exist and updates the existing book when it does. Change IDs remain idempotent: replaying an already-applied change returns `applied: false` and does not apply the change again.

## Release policy

Version `1.1.0` is defined once in `src/books/__init__.py` and exposed to packaging through setuptools dynamic metadata. Core runtime dependencies are installed by the base package. Optional integrations: install `books[barcode]` to enable the ZXing C++ decoder, `books[crypto]` for encrypted backups (cryptography), `books[excel]` for Excel reports (openpyxl), `books[pdf]` for PDF reports (reportlab), or `books[reports]` for both report formats. The scanner also supports injected decoders without that dependency and reports an actionable error when the default decoder is unavailable.

The reproducible release gate builds both sdist and wheel, installs the wheel in an isolated environment, verifies installed metadata and source version, runs migration and health, then starts the installed runtime and exercises health, OpenAPI, authenticated MCP, and sync transport. Artifacts are emitted under `dist/` by `python -m build --sdist --wheel`.

A release is accepted only when clean-database migration, existing-database migration idempotency, REST/MCP runtime, offline smoke, full pytest, lint, Docker build, and the clean wheel-install/package runtime gate are green in CI. Release tags are created only from the verified main commit after that gate passes.

See [Release Governance](docs/RELEASE-GOVERNANCE.md) for the branch-protection policy, release checklist, tag rules, and final release boundary.


## Scheduled automatic backups

The HTTP/MCP runtime can run scheduled SQLite backups in its own managed
background worker. Set `BOOKS_BACKUP_PATH` to a destination such as
`data/backups/latest.sqlite3` to enable it; leaving the variable empty keeps
the scheduler disabled. `BOOKS_BACKUP_INTERVAL_HOURS` defaults to `24` and
`BOOKS_BACKUP_RETENTION` defaults to `5` timestamped snapshots. The stable
destination always points to the latest successful backup, while timestamped
snapshots are pruned to the configured retention count. Backup and state files
are written with owner-only permissions. The worker stops when the runtime
server closes, and failures are recorded in the adjacent `.state` file without
replacing the last successful backup.

The scheduler uses SQLite's online backup API and validates the resulting
database before publishing it. Backups are disabled until a destination is
explicitly configured so the application does not silently create files in an
unexpected location.
