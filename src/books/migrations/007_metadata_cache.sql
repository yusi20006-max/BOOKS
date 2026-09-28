CREATE TABLE IF NOT EXISTS metadata_cache (
    provider TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    language TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (provider, cache_key, language)
);

CREATE INDEX IF NOT EXISTS ix_metadata_cache_fetched_at
    ON metadata_cache(fetched_at);
