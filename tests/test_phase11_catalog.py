from books.catalog import Edition, Translation, Work
from books.catalog_store import CatalogStore
from books.db import Database
from books.series import Series, Volume


def test_phase11_catalog_persists_and_preserves_translations(tmp_path):
    db=Database(tmp_path/"books.sqlite3"); db.migrate(); store=CatalogStore(db)
    store.add_work(Work("w1","کتاب مادر")); store.add_edition(Edition("e1","w1","ناشر",2024))
    store.add_translation(Translation("t1","e1","fa",("tr1",)))
    store.add_series_volume(Series("s1","مجموعه"),Volume("v1","s1","e1",1,"جلد اول"))
    assert store.list_series()[0]["name"]=="مجموعه"
    assert store.list_translations("e1")[0].translator_ids==("tr1",)


def test_phase11_compare_and_deduplicate():
    a=Edition("a","w","ناشر",2024,isbn13="9780306406157")
    b=Edition("b","w","ناشر",2024,isbn13="9780306406157")
    assert store_compare(a,b).score>=100


def store_compare(a,b):
    return CatalogStore(Database(":memory:")).compare(a,b)
