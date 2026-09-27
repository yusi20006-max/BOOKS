from dataclasses import dataclass

from .normalization import normalize_text


@dataclass(frozen=True, slots=True)
class Quote:
    id: str; book_id: str; text: str; page: int|None=None; source: str|None=None
    def __post_init__(self):
        if not self.id.strip() or not self.book_id.strip(): raise ValueError("quote ids are required")
        text=normalize_text(self.text)
        if not text: raise ValueError("quote text is required")
        if self.page is not None and self.page<0: raise ValueError("page must be non-negative")
        object.__setattr__(self,"text",text); object.__setattr__(self,"source",normalize_text(self.source) or None)

@dataclass(frozen=True, slots=True)
class Note:
    id: str; book_id: str; text: str; page: int|None=None
    def __post_init__(self):
        if not self.id.strip() or not self.book_id.strip(): raise ValueError("note ids are required")
        text=normalize_text(self.text)
        if not text: raise ValueError("note text is required")
        if self.page is not None and self.page<0: raise ValueError("page must be non-negative")
        object.__setattr__(self,"text",text)

@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    id: str; label: str; kind: str="concept"
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("node id is required")
        label=normalize_text(self.label)
        if not label: raise ValueError("node label is required")
        object.__setattr__(self,"label",label)

@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    source_id: str; target_id: str; relation: str
    def __post_init__(self):
        if not self.source_id.strip() or not self.target_id.strip(): raise ValueError("edge ids are required")
        relation=normalize_text(self.relation)
        if not relation: raise ValueError("relation is required")
        object.__setattr__(self,"relation",relation)

def knowledge_search(query: str, quotes=(), notes=(), nodes=()):
    q=normalize_text(query).casefold()
    if not q: return []
    items=[]
    for item in (*quotes,*notes,*nodes):
        text=getattr(item,"text",None) or getattr(item,"label","")
        if q in normalize_text(text).casefold(): items.append(item)
    return items
