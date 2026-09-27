from dataclasses import dataclass
from .normalization import normalize_text


@dataclass(frozen=True, slots=True)
class CoverMetadata:
    url: str
    edition_key: str | None = None
    language: str | None = "fa"
    source: str | None = None
    def __post_init__(self):
        url=self.url.strip()
        if not url: raise ValueError("cover url is required")
        object.__setattr__(self,"url",url)
        object.__setattr__(self,"edition_key",normalize_text(self.edition_key) or None)
        object.__setattr__(self,"language",normalize_text(self.language) or None)
        object.__setattr__(self,"source",normalize_text(self.source) or None)
