ALTER TABLE books ADD COLUMN reading_status TEXT NOT NULL DEFAULT 'unread';

CREATE INDEX IF NOT EXISTS ix_books_reading_status
    ON books(reading_status);
