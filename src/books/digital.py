from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class DigitalBook:
    id: str
    book_id: str
    path: str
    format: str
    def __post_init__(self):
        if self.format.lower() not in {"pdf","epub"}: raise ValueError("unsupported digital format")
        if not Path(self.path).name: raise ValueError("digital path is required")


@dataclass(frozen=True, slots=True)
class ReaderPosition:
    attachment_id: str
    page: int = 0
    chapter: str|None = None
    def __post_init__(self):
        if self.page < 0: raise ValueError("page must be non-negative")


@dataclass(frozen=True, slots=True)
class Audiobook:
    id: str
    book_id: str
    path: str
    duration_seconds: int
    position_seconds: int = 0
    speed: float = 1.0
    def __post_init__(self):
        if self.duration_seconds < 0 or self.position_seconds < 0: raise ValueError("audio duration/position must be non-negative")
        if self.position_seconds > self.duration_seconds: raise ValueError("audio position exceeds duration")
        if self.speed <= 0: raise ValueError("audio speed must be positive")
