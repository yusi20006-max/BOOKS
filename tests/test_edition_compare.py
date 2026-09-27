from books.catalog import Edition
from books.edition_compare import compare_editions,is_duplicate_edition,deduplicate_editions

def e(i,**kw): return Edition(i,kw.pop("work_id","w"),**kw)
def test_isbn_and_work_matching():
    a=e("a",isbn13="9780306406157"); b=e("b",isbn13="9780306406157")
    assert "isbn" in compare_editions(a,b).reasons and is_duplicate_edition(a,b)
def test_same_work_without_isbn_is_duplicate():
    a=e("a"); b=e("b",publisher=" ناشر ")
    assert is_duplicate_edition(a,b)
def test_dedup_preserves_first():
    assert [x.id for x in deduplicate_editions([e("a"),e("b")])]==["a"]
