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
