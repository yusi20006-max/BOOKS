from books.ocr import ocr_metadata,correction_payload,scan_to_book_draft

def test_persian_ocr_metadata():
 r=ocr_metadata("کتاب نمونه\\nناشر نمونه\\n978-0-15-601219-5"); assert r.title=="کتاب نمونه" and r.publisher=="ناشر نمونه" and r.isbn=="9780156012195"
def test_correction_payload_is_editable():
 r=scan_to_book_draft("عنوان کتاب"); assert r["title"]=="عنوان کتاب" and "raw_text" in r
