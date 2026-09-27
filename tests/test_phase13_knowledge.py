from books.db import BookRepository, Database
from books.knowledge import KnowledgeEdge, KnowledgeNode
from books.knowledge_store import KnowledgeStore
from books.models import Book

def test_phase13_knowledge_graph_and_unified_search(tmp_path):
    db=Database(tmp_path/"books.sqlite3"); db.migrate(); repo=BookRepository(db); bid=repo.create_book(Book(title="کتاب")); store=KnowledgeStore(db)
    repo.add_note("n1",bid,"یادداشت درباره فلسفه",3); repo.add_quote("q1",bid,"نقل قول درباره فلسفه",4,"منبع")
    store.add_node(KnowledgeNode("k1","فلسفه")); store.add_edge(KnowledgeEdge("k1","q1","مرتبط"))
    assert len(store.search("فلسفه"))==3 and store.nodes()[0].label=="فلسفه"
