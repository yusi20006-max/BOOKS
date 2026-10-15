import json
import subprocess
import sys
from pathlib import Path


def test_performance_baseline_smoke_is_machine_readable():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "benchmark_library.py"),
            "--sizes",
            "25",
            "--repeats",
            "2",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(completed.stdout)
    assert report["schema_version"] == 1
    assert report["benchmark"] == "books-sqlite-library-baseline"
    assert report["results"][0]["dataset_books"] == 25
    operations = report["results"][0]["operations"]
    assert set(operations) == {
        "get_by_id",
        "list_page_50_mid_library",
        "search_exact_token",
        "create_then_delete",
        "count",
        "api_search_cold",
        "api_search_cache_hit",
        "api_list_cache_hit",
    }
    assert all(result["repeats"] == 2 for result in operations.values())
    assert all(result["median_ms"] >= 0 for result in operations.values())
