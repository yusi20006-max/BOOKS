import sqlite3

from books.ui_feedback import error_feedback


def test_connection_failure_has_actionable_persian_recovery_without_raw_details():
    message, recovery = error_feedback(ConnectionError("private endpoint and token"))
    assert "ارتباط" in message
    assert "دوباره تلاش" in recovery
    assert "private endpoint" not in message + recovery
    assert "token" not in message + recovery


def test_file_errors_do_not_expose_local_paths():
    error = FileNotFoundError("/private/home/books.sqlite3")
    message, recovery = error_feedback(error)
    assert "فایل" in message
    assert "مسیر" in recovery
    assert "/private/home" not in message + recovery


def test_database_constraint_failure_suggests_duplicate_review():
    message, recovery = error_feedback(sqlite3.IntegrityError("duplicate key secret"))
    assert "تکراری" in message
    assert "ISBN" in recovery
    assert "duplicate key" not in message + recovery


def test_invalid_input_gets_consistent_recovery_guidance():
    message, recovery = error_feedback(ValueError("raw implementation detail"))
    assert "ورودی معتبر نیست" in message
    assert "قالب فایل" in recovery
    assert "raw implementation detail" not in message + recovery


def test_unexpected_failure_does_not_echo_exception_text():
    message, recovery = error_feedback(RuntimeError("secret database path"))
    assert "در دسترس نیست" in message
    assert "تنظیمات" in recovery
    assert "secret database path" not in message + recovery


def test_storage_errors_are_distinct_from_connectivity_errors():
    message, recovery = error_feedback(OSError("disk full"))
    assert "فایل" in message or "ذخیره‌سازی" in message
    assert "فضای ذخیره‌سازی" in recovery
    assert "disk full" not in message + recovery
