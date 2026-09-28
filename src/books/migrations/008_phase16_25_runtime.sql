CREATE TABLE IF NOT EXISTS reading_sessions (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 0 CHECK(minutes >= 0),
    pages INTEGER NOT NULL DEFAULT 0 CHECK(pages >= 0),
    note TEXT
);

CREATE TABLE IF NOT EXISTS reading_goals (
    id TEXT PRIMARY KEY,
    target_books INTEGER NOT NULL DEFAULT 0,
    target_pages INTEGER NOT NULL DEFAULT 0,
    start_date TEXT,
    end_date TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    page INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    page INTEGER,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS physical_copies (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    condition TEXT NOT NULL DEFAULT 'good',
    status TEXT NOT NULL DEFAULT 'available',
    internal_code TEXT
);

CREATE TABLE IF NOT EXISTS loans (
    id TEXT PRIMARY KEY,
    copy_id TEXT NOT NULL REFERENCES physical_copies(id) ON DELETE CASCADE,
    borrower_id TEXT NOT NULL,
    loaned_on TEXT NOT NULL,
    due_on TEXT,
    returned_on TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_reading_sessions_book ON reading_sessions(book_id);
CREATE INDEX IF NOT EXISTS idx_notes_book ON notes(book_id);
CREATE INDEX IF NOT EXISTS idx_quotes_book ON quotes(book_id);
CREATE INDEX IF NOT EXISTS idx_loans_copy ON loans(copy_id);
