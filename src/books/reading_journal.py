from dataclasses import dataclass
from datetime import date, timedelta
from .normalization import normalize_text

@dataclass(frozen=True, slots=True)
class ReadingGoal:
    id: str; target_books: int=0; target_pages: int=0; start: date|None=None; end: date|None=None
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("goal id is required")
        if self.target_books<0 or self.target_pages<0: raise ValueError("targets must be non-negative")
        if self.start and self.end and self.end<self.start: raise ValueError("end before start")

@dataclass(frozen=True, slots=True)
class ReadingSession:
    id: str; book_id: str; started_at: date; minutes: int=0; pages: int=0; note: str|None=None
    def __post_init__(self):
        if not self.id.strip() or not self.book_id.strip(): raise ValueError("session ids are required")
        if self.minutes<0 or self.pages<0: raise ValueError("session metrics must be non-negative")
        object.__setattr__(self,"note",normalize_text(self.note) or None)

def streak_days(active_dates: set[date]) -> int:
    if not active_dates: return 0
    current=max(active_dates); count=0
    while current in active_dates:
        count+=1; current-=timedelta(days=1)
    return count

def goal_progress(goal: ReadingGoal, books: int=0, pages: int=0) -> dict[str,float]:
    return {"books": (books/goal.target_books*100 if goal.target_books else 0.0), "pages": (pages/goal.target_pages*100 if goal.target_pages else 0.0)}

def calendar_sessions(sessions: list[ReadingSession]) -> dict[date,int]:
    out={}
    for s in sessions: out[s.started_at]=out.get(s.started_at,0)+s.minutes
    return out

def milestones(streak: int) -> tuple[int,...]:
    return tuple(x for x in (7,14,30,60,100) if x<=streak)
