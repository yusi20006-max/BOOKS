import sqlite3

from books.semantic import cosine, HashEmbeddingProvider, hybrid_score, recommend_similar, semantic_search, VectorStore

def test_embedding_is_normalized_and_deterministic():
 p=HashEmbeddingProvider(32); a=p.embed("کتاب فارسی"); assert a==p.embed("کتاب فارسی") and abs(cosine(a,a)-1)<1e-9
def test_vector_store_and_semantic_search():
 c=sqlite3.connect(":memory:"); c.execute("CREATE TABLE embeddings(item_id TEXT PRIMARY KEY,text TEXT,vector_json TEXT NOT NULL)")
 p=HashEmbeddingProvider(); s=VectorStore(c); s.put("1","کتاب فارسی",p.embed("کتاب فارسی")); s.put("2","مهندسی نرم افزار",p.embed("مهندسی نرم افزار"))
 assert s.search(p.embed("کتاب فارسی"),1)[0][1]=="1"; assert semantic_search("کتاب فارسی",[("1","کتاب فارسی"),("2","نرم افزار")],p)[0][1]=="1"
def test_hybrid_and_recommendation():
 assert hybrid_score(1,0)==.45
 assert recommend_similar("1",[("1","کتاب فارسی"),("2","کتاب فارسی"),("3","آشپزی")],HashEmbeddingProvider(),1)[0][1]=="2"
