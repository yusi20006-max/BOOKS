from books.catalog import Edition,Translation
from books.translation_views import translation_view,group_by_translation

def test_translation_view_keeps_translation_identity():
    e=Edition("e","w",publisher=" ناشر ")
    v=translation_view(e,Translation("t","e"," فارسی ",("tr",)))
    assert v.language=="فارسی" and v.translator_ids==("tr",) and "ناشر" in v.label

def test_group_ignores_other_editions():
    e=Edition("e","w"); ts=[Translation("1","e","fa"),Translation("2","x","fa")]
    assert list(group_by_translation(e,ts))==["fa"]
