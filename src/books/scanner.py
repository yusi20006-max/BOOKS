from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .normalization import normalize_isbn, validate_isbn10, validate_isbn13

_ISBN_RE = re.compile(r"(?<!\d)(?:97[89]\d{10}|\d{9}[0-9X])(?!\d)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ScanResult:
    isbn: str | None
    format: str | None
    raw_text: str | None
    error: str | None = None


class BarcodeScanner:
    """Decode ISBN barcodes with an injectable decoder and safe optional runtime dependency."""

    def __init__(self, decoder: Callable[[Any], Any] | None = None) -> None:
        self.decoder = decoder or self._default_decoder

    def scan(self, image: Any) -> ScanResult:
        try:
            decoded = tuple(self.decoder(image) or ())
        except ImportError:
            return ScanResult(None, None, None, "barcode decoder is not installed; install BOOKS with the [barcode] extra")
        except Exception as exc:  # noqa: BLE001
            return ScanResult(None, None, None, str(exc) or "barcode decoding failed")

        for item in decoded:
            text = getattr(item, "text", None) or str(item)
            isbn = self._extract_isbn(text)
            if isbn:
                fmt = "ISBN-13" if len(isbn) == 13 else "ISBN-10"
                return ScanResult(isbn, fmt, text)
        return ScanResult(None, None, None, "no valid ISBN barcode found")

    @staticmethod
    def _extract_isbn(text: str) -> str | None:
        normalized = normalize_isbn(text)
        if normalized and (
            (len(normalized) == 10 and validate_isbn10(normalized))
            or (len(normalized) == 13 and validate_isbn13(normalized))
        ):
            return normalized

        compact_text = normalize_isbn(text) or ""
        for match in _ISBN_RE.finditer(compact_text):
            candidate = normalize_isbn(match.group(0))
            if candidate and (
                (len(candidate) == 10 and validate_isbn10(candidate))
                or (len(candidate) == 13 and validate_isbn13(candidate))
            ):
                return candidate
        return None

    @staticmethod
    def _default_decoder(image: Any) -> Any:
        import zxingcpp

        return zxingcpp.read_barcodes(image)
