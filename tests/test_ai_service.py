import httpx

from books.ai_service import BookAIService, OpenAICompatibleProvider


def test_openai_compatible_provider_uses_chat_completions(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200,json={"choices":[{"message":{"content":"پاسخ فارسی"}}]})
    monkeypatch.setattr(httpx,"post",lambda *a,**k:httpx.Client(transport=httpx.MockTransport(handler)).post(*a,**k))
    provider=OpenAICompatibleProvider("http://local/v1","qwen")
    assert provider.complete("سلام")=="پاسخ فارسی"

def test_ai_service_actions_are_composable():
    class Provider:
        name="test"
        def complete(self,prompt): return prompt
    service=BookAIService(Provider())
    assert "خلاصه" in service.summarize("کتاب","متن")
    assert "برنامه" in service.reading_plan("کتابخانه","روزانه ۲۰ صفحه")
