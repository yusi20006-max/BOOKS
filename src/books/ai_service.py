from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .ai import AIProvider, FailoverAI, book_assistant, personalized_reading_plan, summarize_book, summarize_chapter


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 30.0
    name: str = "openai-compatible"

    def complete(self, prompt: str) -> str:
        headers={"Content-Type":"application/json"}
        if self.api_key: headers["Authorization"]=f"Bearer {self.api_key}"
        response=httpx.post(self.base_url.rstrip("/")+"/chat/completions",json={"model":self.model,"messages":[{"role":"user","content":prompt}]},headers=headers,timeout=self.timeout)
        response.raise_for_status()
        data=response.json()
        try: return str(data["choices"][0]["message"]["content"])
        except (KeyError,IndexError,TypeError) as exc: raise RuntimeError("AI provider returned an invalid response") from exc


def local_first_provider() -> AIProvider:
    local=OpenAICompatibleProvider(os.getenv("BOOKS_AI_BASE_URL","http://127.0.0.1:8000/v1"),os.getenv("BOOKS_AI_MODEL","local"),os.getenv("BOOKS_AI_API_KEY") or None,name="local-gateway")
    remote_url=os.getenv("BOOKS_AI_FALLBACK_BASE_URL")
    if remote_url:
        remote=OpenAICompatibleProvider(remote_url,os.getenv("BOOKS_AI_FALLBACK_MODEL",""),os.getenv("BOOKS_AI_FALLBACK_API_KEY") or None,name="fallback-gateway")
        return FailoverAI((local,remote))
    return local


class BookAIService:
    def __init__(self, provider: AIProvider): self.provider=provider
    def action(self, action: str, title: str, context: str = "") -> str: return book_assistant(self.provider,action,title,context)
    def summarize(self,title:str,text:str)->str: return summarize_book(self.provider,title,text)
    def summarize_chapter(self,title:str,chapter:str,text:str)->str: return summarize_chapter(self.provider,title,chapter,text)
    def reading_plan(self,library:str,goal:str)->str: return personalized_reading_plan(self.provider,library,goal)
