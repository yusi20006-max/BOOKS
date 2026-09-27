import pytest

from books.credits import PublisherCredit, TranslatorCredit, normalize_translators


def test_multiple_translators_are_preserved():
    assert normalize_translators((" یوسف ", "محمد قاضی", "يوسف")) == ("یوسف", "محمد قاضی")

def test_credits_require_names():
    assert PublisherCredit(" نشر نمونه ").name == "نشر نمونه"
    assert TranslatorCredit("كاظم").name == "کاظم"
    with pytest.raises(ValueError): PublisherCredit(" ")
