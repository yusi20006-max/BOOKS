ALTER TABLE books ADD COLUMN reading_current_page INTEGER NOT NULL DEFAULT 0;
ALTER TABLE books ADD COLUMN reading_progress INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_books_reading_progress
    ON books(reading_progress);
