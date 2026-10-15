# Library performance baseline (Issue #175)

The benchmark records the current SQLite repository performance before caching
or background-job changes. It is deliberately local-only and creates synthetic
records in temporary databases; it never reads the user's configured library
or calls network services.

## Run

From a source checkout with the project dependencies installed:

```sh
python scripts/benchmark_library.py
```

The default workload measures 1,000, 5,000, and 10,000 books with 15 samples per
operation. On a phone or slower storage, start smaller:

```sh
python scripts/benchmark_library.py --sizes 100 1000 --repeats 5 --output /tmp/books-baseline.json
```

For each size, the JSON report records Python/SQLite/platform metadata, database
size, migration and seeding duration, and median/p95/min/max timings for:
- get one book by ID;
- read a 50-book page near the middle of the library;
- search for a unique token in a synthetic title;
- create then delete one temporary book;
- count all books.

Bulk fixture seeding and migrations are reported separately and are excluded
from operation samples. A small warm-up runs before timings. Every workload
checks fixture integrity after measurements. The report is suitable for
before/after comparison on the same machine; no universal latency threshold is
asserted because device, filesystem, Python and SQLite versions vary.

## CI smoke

CI runs a small 100-book / 3-repeat workload to ensure the harness remains
executable and its results are internally consistent. This is not a performance
regression threshold. Save full baseline JSON as a local artifact when planning
an optimization, then rerun the same sizes and repeat count after changes.
