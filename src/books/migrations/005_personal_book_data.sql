CREATE TABLE IF NOT EXISTS book_personal (
    book_id TEXT PRIMARY KEY,
    rating INTEGER,
    note TEXT,
    quote TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS ix_book_personal_rating
    ON book_personal(rating);
