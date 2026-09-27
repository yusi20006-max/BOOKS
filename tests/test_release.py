from books import __version__

def test_release_version(): assert __version__=="1.0.0"

def test_core_modules_import():
 import books.scanner,books.ocr,books.api,books.mcp,books.sync,books.backup,books.reports,books.security,books.performance,books.ux
