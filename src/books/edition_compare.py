from dataclasses import dataclass
from .catalog import Edition
from .normalization import normalize_isbn, normalize_text


@dataclass(frozen=True, slots=True)
class EditionMatch:
    left_id: str
    right_id: str
    score: int
    reasons: tuple[str, ...]

def compare_editions(left: Edition, right: Edition) -> EditionMatch:
    reasons=[]; score=0
    li={normalize_isbn(left.isbn10),normalize_isbn(left.isbn13)}-{None}
    ri={normalize_isbn(right.isbn10),normalize_isbn(right.isbn13)}-{None}
    if li & ri: score+=100; reasons.append("isbn")
    if left.work_id == right.work_id: score+=40; reasons.append("work")
    if normalize_text(left.publisher) and normalize_text(left.publisher)==normalize_text(right.publisher): score+=10; reasons.append("publisher")
    if left.publication_year and left.publication_year==right.publication_year: score+=5; reasons.append("year")
    return EditionMatch(left.id,right.id,score,tuple(reasons))

def is_duplicate_edition(left: Edition,right: Edition) -> bool:
    m=compare_editions(left,right)
    return "isbn" in m.reasons or ("work" in m.reasons and m.score>=50)

def deduplicate_editions(editions: list[Edition]) -> list[Edition]:
    kept=[]
    for edition in editions:
        if any(is_duplicate_edition(edition,existing) for existing in kept): continue
        kept.append(edition)
    return kept
