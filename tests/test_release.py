from books import __version__


def test_release_version(): assert __version__=="1.0.0"

def test_core_modules_import():
 import books.api
 import books.backup
 import books.mcp
 import books.ocr
 import books.reports
 import books.scanner
 import books.security