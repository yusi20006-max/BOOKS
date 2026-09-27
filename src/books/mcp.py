from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .db import BookRepository


@dataclass(frozen=True, slots=True)
class Tool:
    name: str; handler: Callable[...,Any]; write: bool=False

class MCPServer:
    def __init__(self, repo: BookRepository): self.repo=repo; self.tools={}; self.audit=[]
    def register(self,name:str,handler:Callable[...,Any],*,write:bool=False):
        self.tools[name]=Tool(name,handler,write)
    def call(self,name:str,arguments:dict[str,Any]|None=None,*,confirmed:bool=False,actor:str="local"):
        tool=self.tools.get(name)
        if tool is None: raise KeyError(name)
        if tool.write and not confirmed: raise PermissionError("write confirmation required")
        result=tool.handler(**(arguments or {}))
        self.audit.append({"tool":name,"actor":actor,"write":tool.write})
        return result

def build_server(repo:BookRepository)->MCPServer:
    server=MCPServer(repo)
    server.register("search_books",lambda query,limit=100:[dict(x) for x in repo.search(query,limit)])
    server.register("get_book",lambda book_id: (dict(x) if (x:=repo.get(book_id)) else None))
    server.register("list_library",lambda limit=100:[dict(x) for x in repo.list(limit)])
    server.register("search_notes",lambda query: repo.search(query))
    server.register("get_statistics",repo.reading_statistics)
    server.register("delete_book",repo.delete,write=True)
    return server
