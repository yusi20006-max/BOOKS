from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True, slots=True)
class Acquisition:
    copy_id: str
    owner_id: str|None = None
    source: str|None = None
    acquired_on: date|None = None
    price: float|None = None
    def __post_init__(self):
        if not self.copy_id.strip(): raise ValueError("copy id is required")
        if self.price is not None and self.price < 0: raise ValueError("price must be non-negative")

@dataclass(frozen=True, slots=True)
class Borrower:
    id: str
    name: str
    phone: str|None = None


@dataclass(frozen=True, slots=True)
class Loan:
    copy_id: str
    borrower_id: str
    loaned_on: date
    due_on: date|None = None
    returned_on: date|None = None
    notes: str|None = None
    @property
    def status(self) -> str:
        return "returned" if self.returned_on else "active"
