from dataclasses import dataclass

from .catalog import Edition, Translation
from .normalization import normalize_text

@dataclass(frozen=True, slots=True)
class TranslationView:
    edition_id: str
    language: str
    translator_ids: tuple[str,...]
    label: str

def translation_view(edition: Edition, translation: Translation) -> TranslationView:
    if translation.edition_id != edition.id: raise ValueError("translation does not belong to edition")
    language=normalize_text(translation.language) or "نامشخص"
    publisher=normalize_text(edition.publisher)
    label="ترجمه "+language
    if publisher: label += " — "+publisher
    return TranslationView(edition.id,language,tuple(translation.translator_ids),label)

def group_by_translation(edition: Edition, translations: list[Translation]) -> dict[str, list[TranslationView]]:
    out={}
    for t in translations:
        if t.edition_id != edition.id: continue
        key=normalize_text(t.language) or "نامشخص"
        out.setdefault(key,[]).append(translation_view(edition,t))
    return out
