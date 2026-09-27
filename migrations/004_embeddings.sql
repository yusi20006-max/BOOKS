CREATE TABLE IF NOT EXISTS embeddings (
 item_id TEXT PRIMARY KEY,
 text TEXT NOT NULL,
 vector_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_embeddings_updated ON embeddings(updated_at);
