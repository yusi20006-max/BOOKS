# Runtime Observability and Diagnostics

BOOKS runtime emits one-line JSON diagnostics to standard error through Python's
standard logging system. Logs suit local development, container collection, and
offline-first deployments; no remote telemetry service is required.

## Configuration

- `BOOKS_LOG_LEVEL`: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, or
  `CRITICAL`. Invalid values stop runtime startup with an actionable error.
- Each normal HTTP response includes an `X-Request-ID` header. Include that ID
  when reporting a server-side failure so the corresponding event can be found.
- Request summaries include method, normalized route template, status, duration
  in milliseconds, and request ID. Book IDs are represented as `/v1/books/{id}`;
  query strings are never logged.

## Privacy and security contract

The logger uses an allow-list of fields. It never records Authorization headers,
bearer tokens, cookies, request/response bodies, query strings, book titles,
notes, user-supplied exception messages, database paths, or client IP addresses.
Unexpected server errors return the stable public response
`{"error":"internal error"}`; the diagnostic event records the exception class,
not its message or traceback. Validation errors remain client-safe and are
returned as before. MCP backend failures produce a generic JSON-RPC
`internal error` while recording the exception class.

Logs may still reveal operational metadata such as route, status, and timing.
Treat log files as operational data, apply restrictive filesystem permissions,
and define retention in the hosting environment. Do not enable third-party log
shipping without reviewing its privacy and retention policy.

## Troubleshooting

1. Capture the `X-Request-ID` from the failed response.
2. Find the matching JSON event in runtime stderr/container logs.
3. Check `event`, `route`, `status`, `duration_ms`, and `error_type`.
4. For `/health?deep=1` returning 503, check database readability and missing
   schema tables. Plain `/health` is intentionally only a cheap liveness probe.
5. Reproduce locally with `BOOKS_LOG_LEVEL=DEBUG`; do not paste tokens,
   private library content, or unredacted logs into public issues.

## Verification

Regression coverage in `tests/test_observability.py` verifies JSON format,
field allow-listing, request correlation, safe route normalization, generic
client errors, and non-disclosure of token/query/exception contents.
