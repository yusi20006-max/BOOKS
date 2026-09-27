import importlib
import re
from pathlib import Path

from books import __version__


def test_release_version(): assert __version__=="1.0.0"

def test_core_modules_import():
    modules = [
        "books.api",
        "books.backup",
        "books.mcp",
        "books.ocr",
        "books.reports",
        "books.scanner",
    ]
    for module in modules:
        importlib.import_module(module)


def test_packaging_version_is_single_source():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in content
    assert not re.search(r'^version\\s*=\\s*["\\\']', content, re.MULTILINE)
