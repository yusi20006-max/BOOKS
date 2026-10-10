# BOOKS 1.1.0 Release

BOOKS is a Persian-first, offline-first personal library application.

## Upgrade

1. Back up the existing SQLite database before upgrading.
2. Install the new application version.
3. Start the application once; versioned migrations are applied automatically.
4. Verify the library, reading progress, personal data, and backup/restore workflow.

## Data safety

Backups should be validated before restore. Restore over an existing database requires explicit overwrite confirmation.

## Production checklist

- Run the full test suite and lint checks in CI.
- Verify SQLite migrations from a clean database and an existing database.
- Verify Persian RTL/mobile flows.
- Verify scanner/OCR, API, MCP, sync, backup, analytics, security and performance contracts.
- Do not commit API keys or provider credentials.

## Versioning

The package follows semantic versioning. Database migrations are monotonically numbered and must never be rewritten after release.
