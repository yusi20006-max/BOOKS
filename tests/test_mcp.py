import pytest

from books.mcp import build_server


class R:
 def search(self,q,limit=100): return [{"q":q}]
 def get(self,i): return {"id":i}
 def list(self,l=100,o=0): return [{"id":"1"}]
 def reading_statistics(self): return {"book_count":1}
 def delete(self,i): return True

def test_read_tools_and_audit():
  s=build_server(R()); result=s.call("search_books",{"query":"کتاب"}); assert result[0]["q"]=="کتاب"
  assert result[0]["authors"]==[] and result[0]["source_ids"]=={}; assert s.audit[-1]["write"] is False
def test_write_requires_confirmation():
 s=build_server(R())
 with pytest.raises(PermissionError): s.call("delete_book",{"i":"1"})
 assert s.call("delete_book",{"i":"1"},confirmed=True) is True


def _repo_with_note_and_quote(tmp_path):
    from books.db import BookRepository, Database
    from books.models import Book

    db = Database(tmp_path / "mcp.sqlite3")
    db.migrate()
    repo = BookRepository(db)
    book_id = repo.create_book(Book(title="کتاب آزمون", authors=("نویسنده آزمون",)))
    repo.add_note("note-1", book_id, "یادداشت آزمون درباره فصل اول", page=12)
    repo.add_quote("quote-1", book_id, "نقل‌قول آزمون از متن اصلی", page=20, source="صفحه ۲۰")
    return repo, book_id


def test_search_notes_returns_note_and_quote_records_not_books(tmp_path):
    repo, book_id = _repo_with_note_and_quote(tmp_path)
    server = build_server(repo)
    rows = server.call("search_notes", {"query": "آزمون"})
    assert {row["kind"] for row in rows} == {"note", "quote"}
    for row in rows:
        assert "title" not in row
        assert "authors_json" not in row
        assert "isbn13" not in row
        assert row["book_id"] == book_id
    note = next(row for row in rows if row["kind"] == "note")
    assert note["id"] == "note-1"
    assert note["text"] == "یادداشت آزمون درباره فصل اول"
    assert note["page"] == 12
    assert note["created_at"]
    quote = next(row for row in rows if row["kind"] == "quote")
    assert quote["id"] == "quote-1"
    assert quote["source"] == "صفحه ۲۰"


def test_search_notes_no_match_and_blank_queries_return_empty(tmp_path):
    repo, _ = _repo_with_note_and_quote(tmp_path)
    server = build_server(repo)
    assert server.call("search_notes", {"query": "عبارتی-که-وجود-ندارد"}) == []
    assert server.call("search_notes", {"query": ""}) == []
    assert server.call("search_notes", {"query": "   "}) == []


def test_search_notes_argument_shape_errors_map_like_before(tmp_path):
    repo, _ = _repo_with_note_and_quote(tmp_path)
    server = build_server(repo)
    with pytest.raises(KeyError):
        server.call("unknown_tool", {})
    with pytest.raises(TypeError):
        server.call("search_notes", {"unexpected": "x"})
