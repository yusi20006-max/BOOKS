from __future__ import annotations

import json
from dataclasses import dataclass

from .db import Database
from .search_ranking import rank
from .semantic import EmbeddingProvider, HashEmbeddingProvider, VectorStore, hybrid_score


@dataclass(frozen=True, slots=True)
class SearchResult:
    book_id: str
    title: str
    lexical: float
    semantic: float
    score: float


class SemanticLibraryService:
    def __init__(self, db: Database, provider: EmbeddingProvider | None = None):
        self.db=db; self.provider=provider or HashEmbeddingProvider()
    def _documents(self)->list[tuple[str,str]]:
        with self.db.connect() as conn: rows=conn.execute("SELECT id,title,authors_json,summary,subjects_json FROM books ORDER BY id").fetchall()
        docs=[]
        for r in rows:
            parts=[r["title"],*json.loads(r["authors_json"] or "[]"),r["summary"] or "",*json.loads(r["subjects_json"] or "[]")]
            docs.append((r["id"]," ".join(parts)))
        return docs
    def rebuild(self)->int:
        count=0
        for item_id,text in self._documents():
            with self.db.connect() as conn: VectorStore(conn).put(item_id,text,self.provider.embed(text))
            count+=1
        return count
    def search(self,query:str,limit:int=10,lexical_weight:float=.45)->list[SearchResult]:
        if not query.strip(): return []
        qv=self.provider.embed(query)
        with self.db.connect() as conn:
            titles={r["id"]:r["title"] for r in conn.execute("SELECT id,title FROM books") }
        with self.db.connect() as conn: semantic_rows=VectorStore(conn).search(qv,max(limit*4,limit))
        results=[]
        for semantic_value,item_id,_ in semantic_rows:
            title=titles.get(item_id,"")
            lexical=rank(query,title,())/130
            results.append(SearchResult(item_id,title,lexical,semantic_value,hybrid_score(lexical,semantic_value,lexical_weight)))
        return sorted(results,key=lambda x:(x.score,x.book_id),reverse=True)[:limit]
    def recommend(self,book_id:str,limit:int=5)->list[SearchResult]:
        docs=self._documents(); target=dict(docs).get(book_id)
        if target is None: raise ValueError("book not found")
        with self.db.connect() as conn: rows=VectorStore(conn).search(self.provider.embed(target),len(docs))
        return [SearchResult(item_id,item_id,0.0,score,score) for score,item_id,_ in rows if item_id!=book_id][:limit]
