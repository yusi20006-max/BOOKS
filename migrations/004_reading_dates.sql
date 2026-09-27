ALTER TABLE books ADD COLUMN reading_started_at TEXT;
ALTER TABLE books ADD COLUMN reading_finished_at TEXT;

CREATE INDEX IF NOT EXISTS ix_books_reading_started_at
    ON books(reading_started_at);
