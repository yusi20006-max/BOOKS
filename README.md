# BOOKS

Persian-first, offline-first personal library.

## Runtime API

Run `python -m books.runtime --host 127.0.0.1 --port 8080 --db books.sqlite3`. Configure `BOOKS_HOST`, `BOOKS_PORT`, `BOOKS_DB_PATH`, and optional `BOOKS_API_TOKEN`. REST is exposed under `/v1`, OpenAPI at `/openapi.json`, and MCP JSON-RPC 2.0 at `POST /mcp`. The Streamlit UI remains the user-facing application.

## Sync contract

The runtime sync endpoint accepts book changes using `create`, `update`, `upsert`, and `delete` operations. `upsert` creates the book when `entity_id` does not exist and updates the existing book when it does. Change IDs remain idempotent: replaying an already-applied change returns `applied: false` and does not apply the change again.

## Release policy

Version `1.0.1` is defined once in `src/books/__init__.py` and exposed to packaging through setuptools dynamic metadata. Core runtime dependencies are installed by the base package. Barcode decoding is an optional integration: install `books[barcode]` to enable the ZXing C++ decoder. The scanner also supports injected decoders without that dependency and reports an actionable error when the default decoder is unavailable.

The reproducible release gate builds both sdist and wheel, installs the wheel in an isolated environment, verifies installed metadata and source version, runs migration and health, then starts the installed runtime and exercises health, OpenAPI, authenticated MCP, and sync transport. Artifacts are emitted under `dist/` by `python -m build --sdist --wheel`.

A release is accepted only when clean-database migration, existing-database migration idempotency, REST/MCP runtime, offline smoke, full pytest, lint, Docker build, and the clean wheel-install/package runtime gate are green in CI. Release tags are created only from the verified main commit after that gate passes.

See [Release Governance](docs/RELEASE-GOVERNANCE.md) for the branch-protection policy, release checklist, tag rules, and final release boundary.
