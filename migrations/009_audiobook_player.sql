CREATE TABLE IF NOT EXISTS audiobooks (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    format TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK(duration_seconds >= 0),
    position_seconds INTEGER NOT NULL DEFAULT 0 CHECK(position_seconds >= 0),
    speed REAL NOT NULL DEFAULT 1.0 CHECK(speed > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audiobooks_book ON audiobooks(book_id);
