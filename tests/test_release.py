import importlib

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
