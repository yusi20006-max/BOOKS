from books.normalization import normalize_isbn

def test_persian_digits_and_unicode_dashes_are_canonicalized():
    assert normalize_isbn("۹۷۸–۰–۳۰۶–۴۰۶۱۵–۷") == "9780306406157"
    assert normalize_isbn("۹۷۸‌۰‌۳۰۶‌۴۰۶۱۵‌۷") == "9780306406157"
