"""Static regression for issue #335.

Streamlit >= 1.49 deprecated ``use_container_width`` in favour of
``width="stretch"`` / ``width="content"``; the removal deadline sits inside
the declared ``streamlit>=1.38,<2`` range. This test keeps the deprecated
token out of the source tree so the migration cannot silently regress.
"""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def test_source_contains_no_use_container_width():
    offenders = sorted(
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if "use_container_width" in path.read_text(encoding="utf-8")
    )
    assert offenders == [], f"deprecated use_container_width found in: {offenders}"
