import pytest
from books.api import BooksAPI,RateLimiter,APIError
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
