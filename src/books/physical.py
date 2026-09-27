from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Location:
    id: str
    building: str|None=None
    room: str|None=None
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("location id is required")


@dataclass(frozen=True, slots=True)
class ShelfPosition:
    location_id: str
    shelf: str
    level: int = 1
    position: int = 1
    def __post_init__(self):
        if self.level < 1 or self.position < 1: raise ValueError("shelf coordinates must be positive")


@dataclass(frozen=True, slots=True)
class PhysicalCopy:
    id: str
    edition_id: str
    condition: str = "good"
    internal_code: str|None = None
    status: str = "available"
    def __post_init__(self):
        if self.status not in {"available","on_loan","lost"}: raise ValueError("invalid copy status")
        if self.condition not in {"new","good","fair","poor","damaged"}: raise ValueError("invalid copy condition")


import hashlib

def make_internal_qr_payload(copy_id: str) -> str:
    if not copy_id.strip(): raise ValueError("copy id is required")
    return "books://copy/" + copy_id.strip()

def location_scan_token(location_id: str) -> str:
    if not location_id.strip(): raise ValueError("location id is required")
    return "books://location/" + location_id.strip()
