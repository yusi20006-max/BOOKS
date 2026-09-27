from dataclasses import dataclass
from collections.abc import Sequence
from typing import Protocol

class AIProvider(Protocol):
    name: str
    def complete(self, prompt: str) -> str: ...

@dataclass(frozen=True, slots=True)
class LocalGatewayProvider:
    client: AIProvider
    name: str = "local-gateway"
    def complete(self, prompt: str) -> str: return self.client.complete(prompt)

@dataclass(frozen=True, slots=True)
class FailoverAI:
    providers: Sequence[AIProvider]
    def complete(self, prompt: str) -> str:
        errors=[]
        for provider in self.providers:
            try: return provider.complete(prompt)
            except RuntimeError as exc: errors.append(f"{provider.name}: {exc}")
        raise RuntimeError("all AI providers failed: " + "; ".join(errors))

def book_assistant(provider: AIProvider, action: str, title: str, context: str = "") -> str:
    if action not in {"summary","questions","recommendation","insights"}: raise ValueError("unsupported AI action")
    prompt=f"کتاب: {title}\nعمل: {action}\nزمینه: {context}".strip()
    return provider.complete(prompt)

def summarize_book(provider: AIProvider, title: str, text: str) -> str:
    return provider.complete(f"خلاصه کتاب «{title}»:\n{text}")

def summarize_chapter(provider: AIProvider, title: str, chapter: str, text: str) -> str:
    return provider.complete(f"خلاصه فصل «{chapter}» از «{title}»:\n{text}")

def personalized_reading_plan(provider: AIProvider, library: str, goal: str) -> str:
    return provider.complete(f"برنامه مطالعه شخصی\nهدف: {goal}\nکتابخانه:\n{library}")
