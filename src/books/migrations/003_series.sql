CREATE TABLE IF NOT EXISTS series (
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 description TEXT
);
CREATE TABLE IF NOT EXISTS series_volumes (
 id TEXT PRIMARY KEY,
 series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
 edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
 volume_number INTEGER NOT NULL CHECK(volume_number > 0),
 title TEXT,
 UNIQUE(series_id, volume_number),
 UNIQUE(series_id, edition_id)
);
CREATE INDEX IF NOT EXISTS idx_series_volumes_series ON series_volumes(series_id, volume_number);
