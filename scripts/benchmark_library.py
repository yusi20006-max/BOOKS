#!/usr/bin/env python3
"""Reproducible, local-only SQLite library performance baseline (issue #175).

This is a measurement harness, not a pass/fail latency gate. Results depend on
hardware, filesystem, Python/SQLite versions, and dataset size; compare runs on
the same machine and environment.
"""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from books.api import BooksAPI, _READ_CACHE
from books.db import BookRepository, Database


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.5)))
    return round(ordered[index], 3)


def measure(
    operation: Callable[[], object], repeats: int, *, before: Callable[[], object] | None = None
) -> dict[str, float | int]:
    samples = []
    for _ in range(repeats):
        if before is not None:
            before()
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "repeats": repeats,
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": percentile(samples, 0.95),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def seed_library(db: Database, size: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute("BEGIN")
        conn.executemany(
            """INSERT INTO books
               (id, title, authors_json, translators_json, genres_json,
                subjects_json, source_ids_json, summary, notes, created_at, updated_at)
               VALUES (?, ?, '[]', '[]', '[]', '[]', '{}', ?, ?, ?, ?)""",
            (
                (
                    f"baseline-{index:08d}",
                    f"کتاب آزمون {index:08d} loadtoken-{index:08d}",
                    f"خلاصهٔ آزمایشی {index:08d}",
                    f"یادداشت آزمایشی {index:08d}",
                    now,
                    now,
                )
                for index in range(size)
            ),
        )
        conn.commit()


def run_size(size: int, repeats: int, root: Path) -> dict[str, object]:
    db_path = root / f"library-{size}.sqlite3"
    db = Database(db_path)
    migration_started = time.perf_counter()
    db.migrate()
    migration_ms = round((time.perf_counter() - migration_started) * 1000, 3)
    seed_started = time.perf_counter()
    seed_library(db, size)
    seed_ms = round((time.perf_counter() - seed_started) * 1000, 3)
    repo = BookRepository(db)
    target_id = f"baseline-{size // 2:08d}"
    search_term = f"loadtoken-{size // 2:08d}"
    temporary_book = {
        "id": "baseline-temporary-write",
        "title": "کتاب موقت آزمون عملکرد",
        "authors_json": "[]",
        "translators_json": "[]",
        "genres_json": "[]",
        "subjects_json": "[]",
        "source_ids_json": "{}",
    }

    def create_delete() -> None:
        repo.create(temporary_book)
        repo.delete(temporary_book["id"])

    # Warm up SQLite/Python paths before recording repeatable operation samples.
    repo.get(target_id)
    repo.list(limit=50, offset=max(0, size // 2 - 25))
    repo.search(search_term, limit=20)
    measurements = {
        "get_by_id": measure(lambda: repo.get(target_id), repeats),
        "list_page_50_mid_library": measure(
            lambda: repo.list(limit=50, offset=max(0, size // 2 - 25)), repeats
        ),
        "search_exact_token": measure(lambda: repo.search(search_term, limit=20), repeats),
        "create_then_delete": measure(create_delete, repeats),
        "count": measure(repo.count, repeats),
    }

    # Measure the API cache independently from the underlying repository scan.
    # Cold samples clear only the in-process cache before timing; warm samples
    # prime once and then time repeated hits against an unchanged SQLite file.
    api = BooksAPI(repo)
    api_search = lambda: api.request("GET", "/v1/search", query={"q": search_term})
    api_list = lambda: api.request(
        "GET", "/v1/books",
        query={"limit": "50", "offset": str(max(0, size // 2 - 25))},
    )
    measurements["api_search_cold"] = measure(api_search, repeats, before=_READ_CACHE.clear)
    _READ_CACHE.clear()
    api_search()
    measurements["api_search_cache_hit"] = measure(api_search, repeats)
    _READ_CACHE.clear()
    api_list()
    measurements["api_list_cache_hit"] = measure(api_list, repeats)
    assert repo.count() == size, "benchmark fixture count drifted"
    assert repo.get(target_id) is not None, "get benchmark fixture missing"
    assert repo.search(search_term, limit=20), "search benchmark fixture missing"
    assert len(repo.list(limit=50, offset=max(0, size // 2 - 25))) <= 50
    return {
        "dataset_books": size,
        "database_bytes": db_path.stat().st_size,
        "migration_ms": migration_ms,
        "seed_ms_excluded_from_operation_timings": seed_ms,
        "operations": measurements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes", nargs="+", type=int, default=[1000, 5000, 10000],
        help="library sizes to measure (default: 1000 5000 10000)",
    )
    parser.add_argument("--repeats", type=int, default=15, help="samples per operation (default: 15)")
    parser.add_argument("--output", type=Path, help="optional path to write the JSON report")
    args = parser.parse_args()
    if not args.sizes or any(size < 1 for size in args.sizes):
        parser.error("--sizes must contain positive integers")
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    with tempfile.TemporaryDirectory(prefix="books-perf-baseline-") as temporary:
        root = Path(temporary)
        report = {
            "schema_version": 1,
            "benchmark": "books-sqlite-library-baseline",
            "environment": {
                "python": __import__("platform").python_version(),
                "sqlite": __import__("sqlite3").sqlite_version,
                "platform": __import__("platform").platform(),
            },
            "notes": [
                "Local synthetic data only; no network calls or personal library access.",
                "Seed time is reported separately and excluded from operation timings.",
                "Latency values are observations, not portable CI thresholds.",
                "API cache-hit measurements are distinct from cold repository timings.",
                "Compare before/after runs on the same device and software environment.",
            ],
            "results": [run_size(size, args.repeats, root) for size in args.sizes],
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
