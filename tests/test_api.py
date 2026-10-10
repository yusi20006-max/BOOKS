import pytest

from books.api import APIError, BooksAPI, RateLimiter


class R:
 def list(self,*a): return []
 def search(self,*a): return []
 def get(self,*a): return None

def test_auth_and_openapi():
 api=BooksAPI(R(),token="x"); assert api.openapi()["openapi"]=="3.0.3"; assert api.request("GET","/v1/books",token="x")==[]
 with pytest.raises(APIError) as e: api.request("GET","/v1/books",token="bad")
 assert e.value.status==401
def test_rate_limit():
  api=BooksAPI(R(),limiter=RateLimiter(1,60)); api.request("GET","/v1/books")
  with pytest.raises(APIError) as e: api.request("GET","/v1/books"); assert e.value.status==429

def test_book_serialization_returns_structured_fields(tmp_path):
  from books.db import BookRepository, Database
  from books.models import Book
  db=Database(tmp_path/"books.sqlite3"); db.migrate(); repo=BookRepository(db)
  book_id=repo.create_book(Book(title="T",authors=("A1",),translators=("T1",),genres=("G1",),subjects=("S1",),source_ids={"gb":"1"},notes="n"))
  api=BooksAPI(repo)
  for payload in (api.request("GET","/v1/books"), api.request("GET","/v1/search",query={"q":"T"}), [api.request("GET",f"/v1/books/{book_id}")]):
    row=payload[0]
    assert row["authors"]==["A1"] and row["translators"]==["T1"] and row["genres"]==["G1"] and row["subjects"]==["S1"] and row["source_ids"]=={"gb":"1"}
    assert "authors_json" in row  # backward compat: raw columns retained

def test_book_serialization_tolerates_malformed_json():
  from books.api import serialize_book_row
  row=serialize_book_row({"id":"x","authors_json":"not-json","translators_json":None,"genres_json":"[1,","subjects_json":"[]","source_ids_json":"oops"})
  assert row["authors"]==[] and row["translators"]==[] and row["genres"]==[] and row["source_ids"]=={}


def test_openapi_documents_every_implemented_route():
    doc = BooksAPI(R(), token="x").openapi()
    # Single source of truth: every route the runtime actually serves.
    implemented_routes = {
        "/health",
        "/openapi.json",
        "/v1/books",
        "/v1/books/{id}",
        "/v1/search",
        "/v1/sync/changes",
        "/v1/sync/settings",
        "/mcp",
    }
    assert set(doc["paths"]) == implemented_routes
    assert set(doc["paths"]["/v1/sync/changes"]) == {"get", "post"}
    assert set(doc["paths"]["/mcp"]) == {"post"}
    change_schema = doc["components"]["schemas"]["Change"]
    assert set(change_schema["required"]) == {
        "id",
        "entity",
        "entity_id",
        "operation",
        "version",
        "payload",
        "changed_at",
    }
    assert doc["components"]["schemas"]["Error"] == {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {"type": "string"}},
    }


def test_search_requires_a_non_empty_query():
    api = BooksAPI(R(), token="x")
    for missing in (None, {"q": ""}, {"q": "   "}):
        with pytest.raises(APIError) as excinfo:
            api.request("GET", "/v1/search", token="x", query=missing)
        assert excinfo.value.status == 400
        assert excinfo.value.message == "query parameter q must not be empty"
