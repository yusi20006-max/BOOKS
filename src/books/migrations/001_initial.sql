CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    original_title TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]',
    translators_json TEXT NOT NULL DEFAULT '[]',
    publisher TEXT,
    pages INTEGER,
    publication_year INTEGER,
    isbn10 TEXT,
    isbn13 TEXT,
    language TEXT,
    genres_json TEXT NOT NULL DEFAULT '[]',
    subjects_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    cover_url TEXT,
    source_ids_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_books_isbn10
    ON books(isbn10) WHERE isbn10 IS NOT NULL AND isbn10 <> '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_books_isbn13
    ON books(isbn13) WHERE isbn13 IS NOT NULL AND isbn13 <> '';

CREATE INDEX IF NOT EXISTS ix_books_title ON books(title);
CREATE INDEX IF NOT EXISTS ix_books_updated_at ON books(updated_at);
