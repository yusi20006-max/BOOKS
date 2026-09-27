from dataclasses import dataclass
from .normalization import normalize_text, normalize_isbn

@dataclass(frozen=True, slots=True)
class Work:
    id: str
    title: str
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("work id is required")
        title=normalize_text(self.title)
        if not title: raise ValueError("work title is required")
        object.__setattr__(self,"title",title)

@dataclass(frozen=True, slots=True)
class Edition:
    id: str
    work_id: str
    publisher: str|None=None
    publication_year: int|None=None
    isbn10: str|None=None
    isbn13: str|None=None

@dataclass(frozen=True, slots=True)
class Translation:
    id: str
    edition_id: str
    language: str
    translator_ids: tuple[str,...]=()

@dataclass(frozen=True, slots=True)
class Copy:
    id: str
    edition_id: str
    format: str = "physical"
    owner_id: str|None = None
