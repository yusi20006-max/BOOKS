from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from .db import BookRepository

@dataclass(slots=True)
class RateLimiter:
    limit: int=60; window: float=60.0
    hits: dict[str,list[float]]=None
    def __post_init__(self): self.hits={} if self.hits is None else self.hits
    def allow(self,key: str)->bool:
        now=monotonic(); values=[x for x in self.hits.get(key,[]) if now-x<self.window]
        if len(values)>=self.limit: self.hits[key]=values; return False
        values.append(now); self.hits[key]=values; return True

class APIError(Exception):
    def __init__(self,status:int,message:str): self.status=status; self.message=message

class BooksAPI:
    def __init__(self, repo: BookRepository, token: str|None=None, limiter: RateLimiter|None=None):
        self.repo=repo; self.token=token; self.limiter=limiter or RateLimiter()
    def authorize(self, provided: str|None)->None:
        if self.token is not None and provided != self.token: raise APIError(401,"unauthorized")
    def request(self, method:str,path:str,*,token:str|None=None,query:dict[str,str]|None=None,body:dict[str,Any]|None=None,client_id:str="local"):
        self.authorize(token)
        if not self.limiter.allow(client_id): raise APIError(429,"rate limit exceeded")
        query=query or {}; body=body or {}
        if method=="GET" and path=="/v1/books": return [dict(x) for x in self.repo.list(int(query.get("limit",100)),int(query.get("offset",0)))]
        if method=="GET" and path=="/v1/search": return [dict(x) for x in self.repo.search(query.get("q",""),int(query.get("limit",100)))]
        if method=="GET" and path.startswith("/v1/books/"):
            row=self.repo.get(path.rsplit("/",1)[1]);
            if row is None: raise APIError(404,"book not found")
            return dict(row)
        raise APIError(404,"endpoint not found")
    @staticmethod
    def openapi()->dict[str,Any]:
        return {"openapi":"3.0.3","info":{"title":"BOOKS API","version":"1.0.0"},"paths":{"/v1/books":{"get":{}},"/v1/books/{id}":{"get":{}},"/v1/search":{"get":{}}}}
