from datetime import datetime
from books.persian_date import format_jalali

def test_now_is_formatted_as_jalali_date():
    assert format_jalali(datetime(2026,3,21)) == "1405/01/01"
