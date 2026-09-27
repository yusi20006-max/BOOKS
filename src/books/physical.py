from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Location:
    id: str
    building: str|None=None
    room: str|None=None
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("location id is required")
