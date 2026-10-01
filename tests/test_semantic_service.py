from books.db import BookRepository, Database
from books.models import Book
from books.semantic_service import SemanticLibraryService


def test_phase15_rebuild_search_and_recommend(tmp_path):
    db=Database(tmp_path/"books.sqlite3"); db.migrate(); repo=BookRepository(db)
    a=repo.create_book(Book(title="فلسفه",authors=("افلاطون",),summary="اندیشه و فلسفه")); b=repo.create_book(Book(title="آشپزی",summary="غذا و دستور"));
    service=SemanticLibraryService(db); assert service.rebuild()==2
    results=service.search("فلسفه",2); assert results and results[0].book_id==a
    assert service.recommend(a,1) and service.recommend(a,1)[0].book_id==b
