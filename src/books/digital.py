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
