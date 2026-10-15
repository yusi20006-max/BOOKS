# BOOKS Security Threat Model

## Scope and security objective

BOOKS is a Persian-first, offline-first personal library application. This model covers the local Streamlit application, the HTTP runtime/API, SQLite persistence, backup/restore, import/export, MCP tool calls, and optional settings/data synchronization. It records trust assumptions and testable security properties; it is not a claim that a professional penetration test has been performed.

## Assets

- Personal library records, notes, quotes, loans, annotations, and reading history.
- Local SQLite database and backup archives.
- API bearer token and provider credentials (including Google Books API configuration).
- Integrity of synchronized preferences and library changes.
- Availability and recoverability of the local library.

## Trust boundaries and entry points

| Boundary / entry point | Untrusted input | Required controls |
| --- | --- | --- |
| HTTP runtime (GET/POST) | URL, query string, headers, body length, JSON types | Authentication on protected routes, bounded request bodies, strict schema/type checks, rate limiting, generic internal errors |
| Settings sync (/v1/sync/settings) | device ID, key, scalar value, base version, revision cursor | Reject credential-like keys, non-scalar/non-finite/oversized values, invalid versions; optimistic concurrency; authenticated reads and writes |
| Library sync (/v1/sync/changes) | change identifiers, entity, operation, version, payload | Allow-listed entity/operation, typed fields, authenticated writes, idempotency and conflict rules |
| MCP (/mcp) | JSON-RPC method, tool name, arguments, confirmation | Validate request envelope, tool allow-list, permission checks, rate limits, generic handling of unexpected failures |
| Backup restore | archive bytes and overwrite request | Size limit, SQLite/schema validation, explicit overwrite, atomic replacement, restrictive file permissions |
| Import/export | JSON/CSV records and references | Schema allow-list, parameterized SQL, bounded/validated data, no payload-selected SQL identifiers |
| Local filesystem/configuration | environment values, paths, local database files | Loopback-by-default bind, explicit opt-in for non-loopback exposure, owner-only backup files, credentials excluded from synced preferences |

## Threat assessment (STRIDE)

| ID | Threat | Existing / required control | Regression evidence |
| --- | --- | --- | --- |
| S-01 | Unauthenticated caller reads or writes synchronized data | API authorization on both sync endpoints | tests/test_settings_sync_security.py |
| T-01 | Secret is disguised as a preference key (access_key, authorization, bearer/cookie/session identifiers) | Normalize separators and reject credential-like key names at the server boundary and local pull boundary | tests/test_settings_sync_security.py |
| T-02 | Stale device overwrites a newer preference | Version-based optimistic concurrency; HTTP 409 on conflicting stale writes | tests/test_settings_sync.py |
| T-03 | Malformed, non-scalar, non-finite, or oversized preference values | JSON scalar allow-list, allow_nan=False, 4096-byte value cap | tests/test_settings_sync.py, tests/test_settings_sync_security.py |
| I-01 | Credentials leak through synchronized values or error responses | Reject sensitive key names; do not echo submitted values; generic internal errors | tests/test_settings_sync.py, tests/test_settings_sync_security.py |
| D-01 | Oversized HTTP body consumes resources | Runtime rejects bodies over 1 MiB | tests/test_settings_sync_security.py |
| E-01 | Untrusted caller invokes protected route without authorization | BooksAPI authorization before protected operation | tests/test_settings_sync.py, tests/test_settings_sync_security.py |

## Explicit assumptions and residual risks

- A configured sync endpoint is an administrator/user trust decision. This model does not make arbitrary endpoints trustworthy; use HTTPS for non-loopback endpoints and protect the endpoint's bearer token.
- A bearer token is a shared secret, not a per-user identity or fine-grained authorization system. Anyone holding it may exercise the permissions granted to that token.
- Local filesystem access by the same OS account is outside the application's isolation boundary.
- Rate limiting is process-local unless an external shared limiter is configured.
- This is repository-level threat modeling plus regression testing, not a substitute for external penetration testing, dependency review, deployment hardening, or an independent security audit.

## Review checklist

- [x] Enumerated primary HTTP, MCP, database, import/export, and backup entry points.
- [x] Identified sensitive data and trust boundaries.
- [x] Added regression coverage for secret-like sync keys and hostile HTTP input.
- [ ] Review deployment-specific TLS, proxy, token rotation, and network exposure before public deployment.
- [ ] Run a dedicated dependency and secret scan in CI/release pipeline.
