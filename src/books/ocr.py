from dataclasses import dataclass
import re
from .normalization import normalize_isbn, normalize_text

@dataclass(frozen=True, slots=True)
class OCRMetadata:
    title: str|None
    authors: tuple[str,...]
    isbn: str|None
    publisher: str|None
    raw_text: str

def ocr_metadata(text: str) -> OCRMetadata:
    clean=normalize_text(text)
    isbn=normalize_isbn(re.search(r"(?:97[89][\d\s\-\u200c]{10,20}|[\d\s\-\u200c]{9,18}[Xx])",clean).group()) if re.search(r"(?:97[89][\d\s\-\u200c]{10,20}|[\d\s\-\u200c]{9,18}[Xx])",clean) else None
    lines=[x.strip() for x in clean.splitlines() if x.strip()]
    title=lines[0] if lines else None
    return OCRMetadata(title,(),isbn,lines[1] if len(lines)>1 else None,clean)

def copyright_page(text: str) -> OCRMetadata:
    return ocr_metadata(text)

def correction_payload(result: OCRMetadata) -> dict[str,object]:
    return {"title":result.title or "","authors":list(result.authors),"isbn":result.isbn or "","publisher":result.publisher or ""}

def scan_to_book_draft(text: str) -> dict[str,object]:
    result=ocr_metadata(text)
    return correction_payload(result)|{"raw_text":result.raw_text}
