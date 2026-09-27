from dataclasses import dataclass

from .normalization import normalize_text


@dataclass(frozen=True, slots=True)
class Series:
    id: str
    name: str
    description: str | None = None
    def __post_init__(self):
        if not self.id.strip(): raise ValueError("series id is required")
        name=normalize_text(self.name)
        if not name: raise ValueError("series name is required")
        object.__setattr__(self,"name",name)
        object.__setattr__(self,"description",normalize_text(self.description) or None)

@dataclass(frozen=True, slots=True)
class Volume:
    id: str
    series_id: str
    edition_id: str
    number: int
    title: str | None = None
    def __post_init__(self):
        if not self.id.strip() or not self.series_id.strip() or not self.edition_id.strip():
            raise ValueError("volume identifiers are required")
        if self.number < 1: raise ValueError("volume number must be positive")
        object.__setattr__(self,"title",normalize_text(self.title) or None)
