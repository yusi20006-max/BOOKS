CREATE TABLE IF NOT EXISTS works (id TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS editions (id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, publisher TEXT, publication_year INTEGER, isbn10 TEXT, isbn13 TEXT);
CREATE TABLE IF NOT EXISTS translations (id TEXT PRIMARY KEY, edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE, language TEXT NOT NULL, translator_ids_json TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS copies (id TEXT PRIMARY KEY, edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE, format TEXT NOT NULL DEFAULT 'physical', owner_id TEXT);
CREATE INDEX IF NOT EXISTS ix_editions_work ON editions(work_id);
CREATE INDEX IF NOT EXISTS ix_translations_edition ON translations(edition_id);
CREATE INDEX IF NOT EXISTS ix_copies_edition ON copies(edition_id);
