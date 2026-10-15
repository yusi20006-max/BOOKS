# Caching and background work

BOOKS uses bounded, in-process caches for repeat reads and external catalog
searches. No cache is persisted to disk, and no remote cache service is needed.

## SQLite-backed API reads

The REST API caches successful GET responses for up to five seconds, with a
256-entry LRU limit. Keys include a digest of the request method, route, and
query parameters, plus the SQLite database file signature (main file and
-WAL/-SHM sidecars). A database write changes the signature and naturally
invalidates prior entries. In-memory databases and repositories without a
filesystem-backed database bypass this cache. Authentication and rate limiting
run before cache lookup, so a cache hit never bypasses those checks. Cached
payloads are copied on read/write to prevent callers from mutating shared data.

The short TTL is a safety net for filesystems where metadata changes are not
immediately visible; it is not a replacement for transactional consistency.

## External catalog discovery

Successful provider search responses are cached for five minutes, up to 128
entries. The cache key includes the exact trimmed query, language, page offset,
page size, strategy, provider type, and a digest of provider settings. Provider
credentials are never written to logs or stored verbatim in the cache key.
Responses with any provider failure are not cached, so temporary outages can
recover on the next attempt. The cache is process-local and disappears on
restart; offline-first local library behavior is unchanged.

## Background work and lifecycle

Scheduled SQLite backups remain an explicitly configured background worker,
owned by the HTTP server. Set `BOOKS_BACKUP_PATH` to enable it; without that
setting, no scheduler thread is created. The worker creates validated snapshots
atomically, retains the configured number of snapshots, resumes the remaining
interval from its state file, and survives an individual backup failure without
replacing the last successful backup. Server shutdown signals the worker and
joins its thread. Manual and scheduled backups targeting the same destination
are serialized.

This issue does not introduce a second generic task queue: current long-running
background work is scheduled backup creation, while catalog search remains
request-driven and benefits from successful-result caching.

## Validation

- `tests/test_cache.py`: expiry, LRU eviction, and invalid configuration.
- `tests/test_api.py`: repeated API reads, defensive copies, and invalidation
  after a SQLite write.
- `tests/test_discovery.py`: reuse across service instances, cache-key
  dimensions, and not caching provider failures.
- `tests/test_backup_scheduler.py`: worker lifecycle, restart scheduling,
  concurrent manual runs, recovery, and retention.
