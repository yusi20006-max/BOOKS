from __future__ import annotations

from dataclasses import dataclass

from .normalization import normalize_text

@dataclass(frozen=True, slots=True)
class TranslatorCredit:
    name: str
    language_from: str | None = None
    language_to: str | None = "fa"
    def __post_init__(self):
        name = normalize_text(self.name)
        if not name: raise ValueError("translator name is required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "language_from", normalize_text(self.language_from) or None)
        object.__setattr__(self, "language_to", normalize_text(self.language_to) or None)

@dataclass(frozen=True, slots=True)
class PublisherCredit:
    name: str
    imprint: str | None = None
    def __post_init__(self):
        name = normalize_text(self.name)
        if not name: raise ValueError("publisher name is required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "imprint", normalize_text(self.imprint) or None)


def normalize_translators(values):
    return tuple(dict.fromkeys(TranslatorCredit(v).name for v in values if normalize_text(v)))
