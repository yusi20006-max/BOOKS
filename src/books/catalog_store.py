from __future__ import annotations

import json
import uuid
from typing import Any

from .catalog import Edition, Translation, Work
from .db import Database, transaction
from .edition_compare import compare_editions, deduplicate_editions
from .normalization import normalize_text
from .series import Series, Volume


class CatalogStore:
    def __init__(self, db: Database):
        self.db = db

    def add_work(self, work: Work) -> str:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO works(id,title) VALUES(?,?)", (work.id, work.title))
        return work.id

    def add_edition(self, edition: Edition) -> str:
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM works WHERE id=?", (edition.work_id,)).fetchone() is None:
                raise ValueError("work not found")
            conn.execute("INSERT INTO editions(id,work_id,publisher,publication_year,isbn10,isbn13) VALUES(?,?,?,?,?,?)", (edition.id, edition.work_id, normalize_text(edition.publisher) or None, edition.publication_year, edition.isbn10, edition.isbn13))
        return edition.id

    def add_translation(self, translation: Translation) -> str:
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM editions WHERE id=?", (translation.edition_id,)).fetchone() is None:
                raise ValueError("edition not found")
            conn.execute("INSERT INTO translations(id,edition_id,language,translator_ids_json) VALUES(?,?,?,?)", (translation.id, translation.edition_id, normalize_text(translation.language), json.dumps(translation.translator_ids, ensure_ascii=False)))
        return translation.id

    def add_series_volume(self, series: Series, volume: Volume) -> str:
        if volume.series_id != series.id:
            raise ValueError("volume does not belong to series")
        with transaction(self.db) as conn:
            conn.execute("INSERT OR IGNORE INTO series(id,name,description) VALUES(?,?,?)", (series.id, series.name, series.description))
            if conn.execute("SELECT 1 FROM editions WHERE id=?", (volume.edition_id,)).fetchone() is None:
                raise ValueError("edition not found")
            conn.execute("INSERT INTO series_volumes(id,series_id,edition_id,volume_number,title) VALUES(?,?,?,?,?)", (volume.id, volume.series_id, volume.edition_id, volume.number, volume.title))
        return volume.id

    def add_series(self, series: Series) -> str:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO series(id,name,description) VALUES(?,?,?)", (series.id, series.name, series.description))
        return series.id

    def list_series(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows=conn.execute("SELECT * FROM series ORDER BY name").fetchall()
            return [dict(row) for row in rows]

    def list_translations(self, edition_id: str) -> list[Translation]:
        with self.db.connect() as conn:
            rows=conn.execute("SELECT * FROM translations WHERE edition_id=? ORDER BY language,id", (edition_id,)).fetchall()
        return [Translation(row["id"], row["edition_id"], row["language"], tuple(json.loads(row["translator_ids_json"] or "[]"))) for row in rows]

    def list_editions(self) -> list[dict[str, Any]]:
        """Editions with their work title, for selectors and views."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT e.*, w.title AS work_title FROM editions e "
                "JOIN works w ON w.id = e.work_id ORDER BY w.title, e.id"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_volumes(self) -> list[dict[str, Any]]:
        """Series volumes with series and work context, for the page listing."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT v.*, s.name AS series_name, w.title AS work_title "
                "FROM series_volumes v JOIN series s ON s.id = v.series_id "
                "JOIN editions e ON e.id = v.edition_id "
                "JOIN works w ON w.id = e.work_id "
                "ORDER BY s.name, v.volume_number"
            ).fetchall()
        return [dict(row) for row in rows]

    def compare(self, left: Edition, right: Edition):
        return compare_editions(left, right)

    def deduplicate(self, editions: list[Edition]) -> list[Edition]:
        return deduplicate_editions(editions)


def new_id() -> str:
    return str(uuid.uuid4())
