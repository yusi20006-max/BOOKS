import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from .normalization import normalize_text


class EmbeddingProvider(Protocol):
    dimensions: int
    def embed(self, text: str) -> tuple[float,...]: ...

@dataclass(frozen=True, slots=True)
class HashEmbeddingProvider:
    dimensions: int = 64
    def embed(self, text: str) -> tuple[float,...]:
        if self.dimensions<8: raise ValueError("dimensions must be at least 8")
        vector=[0.0]*self.dimensions
        tokens=re.findall(r"\w+",normalize_text(text).casefold())
        for token in tokens:
            h=0
            for ch in token: h=(h*31+ord(ch))%self.dimensions
            vector[h]+=1.0
        norm=math.sqrt(sum(x*x for x in vector)) or 1.0
        return tuple(x/norm for x in vector)

def cosine(left: tuple[float,...],right: tuple[float,...]) -> float:
    if len(left)!=len(right): raise ValueError("vector dimensions differ")
    return sum(a*b for a,b in zip(left,right))

class VectorStore:
    def __init__(self, connection: sqlite3.Connection): self.connection=connection
    def put(self, item_id: str, text: str, vector: tuple[float,...]) -> None:
        import json
        self.connection.execute("INSERT INTO embeddings(item_id,text,vector_json) VALUES(?,?,?) ON CONFLICT(item_id) DO UPDATE SET text=excluded.text,vector_json=excluded.vector_json",(item_id,text,json.dumps(vector)))
        self.connection.commit()
    def search(self, vector: tuple[float,...], limit: int=10):
        import json
        rows=self.connection.execute("SELECT item_id,text,vector_json FROM embeddings").fetchall()
        scored=[(cosine(vector,tuple(json.loads(r[2]))),r[0],r[1]) for r in rows]
        return sorted(scored,reverse=True)[:limit]

def hybrid_score(lexical: float, semantic: float, lexical_weight: float=0.45) -> float:
    if not 0<=lexical_weight<=1: raise ValueError("lexical_weight must be between 0 and 1")
    return lexical*lexical_weight+semantic*(1-lexical_weight)

def semantic_search(query: str, documents: list[tuple[str,str]], provider: EmbeddingProvider, limit: int=10):
    q=provider.embed(query)
    scored=[(cosine(q,provider.embed(text)),item_id,text) for item_id,text in documents]
    return sorted(scored,reverse=True)[:limit]

def recommend_similar(item_id: str, documents: list[tuple[str,str]], provider: EmbeddingProvider, limit: int=5):
    target=dict(documents).get(item_id)
    if target is None: raise ValueError("item not found")
    q=provider.embed(target)
    candidates=[(cosine(q,provider.embed(text)),doc_id,text) for doc_id,text in documents if doc_id!=item_id]
    return sorted(candidates,reverse=True)[:limit]
