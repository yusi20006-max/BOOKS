from dataclasses import dataclass

from books.app import candidate_summary
from books.discovery import MergedDiscoveryItem, SourceProvenance
from books.models import Book


@dataclass
class Page:
    items: tuple
    total_items: int


def test_candidate_summary_is_persian_friendly():
    candidate = MergedDiscoveryItem(
        book=Book(
            title="شازده کوچولو",
            authors=("آنتوان دو سنت اگزوپری",),
            translators=("احمد شاملو",),
            publisher="نشر نمونه",
            publication_year=1400,
            isbn13="9780156012195",
        ),
        confidence=0.95,
        matched_by=("title", "author"),
        provenance=(SourceProvenance("google_books", "g-1"), SourceProvenance("open_library", "ol-1")),
    )
    summary = candidate_summary(candidate)
    assert summary["عنوان"] == "شازده کوچولو"
    assert summary["مترجم"] == "احمد شاملو"
    assert summary["منبع"] == "google_books، open_library"
    assert summary["اطمینان"] == "95%"


def test_candidate_summary_handles_missing_metadata():
    candidate = MergedDiscoveryItem(
        book=Book(title="کتاب نمونه"),
        confidence=0.0,
        matched_by=(),
        provenance=(SourceProvenance("open_library", None),),
    )
    summary = candidate_summary(candidate)
    assert summary["نویسنده"] == "—"
    assert summary["ISBN"] == "—"
    assert summary["سال"] == "—"
