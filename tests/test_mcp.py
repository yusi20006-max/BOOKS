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
