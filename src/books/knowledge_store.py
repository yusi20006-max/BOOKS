from __future__ import annotations

from .db import Database, transaction
from .knowledge import KnowledgeEdge, KnowledgeNode, Note, Quote, knowledge_search
from .normalization import normalize_text


class KnowledgeStore:
    def __init__(self, db: Database): self.db=db
    def add_node(self,node:KnowledgeNode)->str:
        with transaction(self.db) as conn: conn.execute("INSERT INTO knowledge_nodes(id,label,kind) VALUES(?,?,?)",(node.id,node.label,node.kind))
        return node.id
    def add_edge(self,edge:KnowledgeEdge)->None:
        with transaction(self.db) as conn:
            if conn.execute("SELECT 1 FROM knowledge_nodes WHERE id=?",(edge.source_id,)).fetchone() is None: raise ValueError("source node not found")
            conn.execute("INSERT INTO knowledge_edges(source_id,target_id,relation) VALUES(?,?,?)",(edge.source_id,edge.target_id,edge.relation))
    def nodes(self)->list[KnowledgeNode]:
        with self.db.connect() as conn: rows=conn.execute("SELECT * FROM knowledge_nodes ORDER BY label").fetchall()
        return [KnowledgeNode(r["id"],r["label"],r["kind"]) for r in rows]
    def search(self,query:str)->list[object]:
        q=normalize_text(query).casefold()
        if not q:return []
        with self.db.connect() as conn:
            notes=[Note(r["id"],r["book_id"],r["text"],r["page"]) for r in conn.execute("SELECT * FROM notes WHERE lower(text) LIKE ?",(f"%{q}%",)).fetchall()]
            quotes=[Quote(r["id"],r["book_id"],r["text"],r["page"],r["source"]) for r in conn.execute("SELECT * FROM quotes WHERE lower(text) LIKE ?",(f"%{q}%",)).fetchall()]
        return knowledge_search(query,quotes,notes,self.nodes())
