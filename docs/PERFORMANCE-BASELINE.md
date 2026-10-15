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


## Recorded baseline — 2026-10-15

The first full baseline ran on GitHub Actions run #520, using Python 3.12.15, SQLite 3.45.1, and an Ubuntu x86_64 GitHub-hosted runner. Each operation has 15 samples after warm-up. Values are milliseconds; these numbers are a reference for same-runner comparisons, not device-independent service-level objectives.

| Synthetic books | Get by ID median / p95 | List 50 at middle median / p95 | Search median / p95 | Create + delete median / p95 | Count median / p95 | DB size |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0.470 / 0.514 | 2.680 / 2.893 | 141.752 / 143.201 | 2.989 / 3.799 | 0.425 / 0.448 | 917,504 bytes |
| 5,000 | 0.375 / 0.423 | 11.135 / 11.471 | 704.927 / 710.219 | 3.054 / 4.097 | 0.446 / 0.503 | 3,178,496 bytes |
| 10,000 | 0.376 / 0.425 | 26.153 / 26.447 | 1,410.447 / 1,438.239 | 2.966 / 3.338 | 0.385 / 0.415 | 6,004,736 bytes |

### Findings before optimization

- Search is the dominant measured cost: the median rises from about 142 ms at 1,000 records to about 1.41 s at 10,000. This is consistent with the current multi-column normalized LIKE scan and makes search the primary candidate for the next optimization issue.
- A middle-of-library 50-book page grows from 2.68 ms to 26.15 ms as offset and dataset size increase.
- Point lookup and create/delete remain approximately stable in this synthetic workload.
- These are repository-level SQLite measurements, not concurrent HTTP load, Streamlit rendering, cold-start, or real-device measurements. Do not claim those scenarios are covered.

The raw JSON report is retained as the workflow artifact for run #520 for 30 days. Future baseline workflow runs produce a new artifact; use identical sizes, repeat count, and runner class for meaningful comparisons.


## Post-change rerun — 2026-10-15

The expanded harness ran successfully in CI run #539 (Python 3.12.15, SQLite
3.45.1, Ubuntu x86_64 GitHub-hosted runner; 15 samples per operation).

| Synthetic books | Repository search median / p95 | Cold API search median / p95 | Warm API search-cache hit median / p95 | Warm API list-cache hit median / p95 |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | 83.291 / 84.821 ms | 80.152 / 81.101 ms | 0.048 / 0.060 ms | 0.520 / 0.581 ms |
| 5,000 | 404.152 / 432.240 ms | 406.026 / 438.415 ms | 0.046 / 0.059 ms | 0.511 / 0.549 ms |
| 10,000 | 823.506 / 847.677 ms | 803.258 / 841.887 ms | 0.047 / 0.060 ms | 0.522 / 0.546 ms |

### Interpretation

- Warm API cache hits are approximately 0.05 ms for search and 0.51–0.52 ms for
  a 50-book list page in this runner, versus roughly 80–823 ms for cold search.
  These figures quantify the benefit of repeating an identical API request
  while the database signature is unchanged.
- Cold repository search still scales with library size: its median at 10,000
  books is about 9.9 times the 1,000-book result. The cache does not accelerate
  a first-time query or a query after the database changes; query/index
  optimization remains a separate follow-up if that latency is unacceptable.
- The earlier baseline and this run show material runner-to-run variation for
  cold search, so the values should not be interpreted as a controlled before /
  after percentage improvement. The cache-hit measurements are new in this run
  and were not available in the original baseline.
- Full report: GitHub Actions run #539, artifact `books-performance-baseline-f3c58dbf24b4cccc2df24b22bde6563d94dbeeec`.
