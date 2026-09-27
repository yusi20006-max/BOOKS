from __future__ import annotations

import re
import unicodedata

_ARABIC_TO_ASCII = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

# Canonical form is for matching/deduplication; display text is never replaced by it.
_YEH_MAP = str.maketrans({"ي": "ی", "ى": "ی"})
_KEH_MAP = str.maketrans({"ك": "ک"})
_ZWNJ_RE = re.compile(r"\s*\u200c\s*")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = text.translate(_YEH_MAP).translate(_KEH_MAP)
    text = text.translate(_ARABIC_TO_ASCII)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = _ZWNJ_RE.sub("\u200c", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_isbn(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.translate(_ARABIC_TO_ASCII)
    compact = re.sub(r"[\s-]+", "", value).upper()
    return compact or None


def validate_isbn10(value: str) -> bool:
    value = normalize_isbn(value)
    if value is None or len(value) != 10 or not re.fullmatch(r"[0-9]{9}[0-9X]", value):
        return False
    total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(value))
    return total % 11 == 0


def validate_isbn13(value: str) -> bool:
    value = normalize_isbn(value)
    if value is None or len(value) != 13 or not value.isdigit():
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(ch) for i, ch in enumerate(value))
    return total % 10 == 0
