from datetime import datetime, timezone

from books.persian_date import format_jalali

def test_now_is_formatted_as_jalali_date():
    assert format_jalali(datetime(2026, 3, 21, tzinfo=timezone.utc)) == "1405/01/01"
