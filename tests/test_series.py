from books.series import Series, Volume
import pytest

def test_series_and_volume_are_persian_first():
    s=Series("s1","  مجموعه  بنیاد  "," توضیح ")
    v=Volume("v1","s1","e1",1," جلد اول ")
    assert s.name=="مجموعه بنیاد"
    assert s.description=="توضیح"
    assert v.title=="جلد اول"

def test_volume_number_is_positive():
    with pytest.raises(ValueError): Volume("v","s","e",0)
