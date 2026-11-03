import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.services.ai_service import AIService, AIProviderError


@pytest.mark.parametrize("budget", [8, 64, 4096, 8192])
async def test_gemini_omits_store_and_reserves_thinking_budget(monkeypatch, budget):
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "PASS"}}]})

    service = AIService()
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        assert await service.chat_api("Verify", "Test", budget) == "PASS"
        payload = json.loads(requests[0].content)
        assert "store" not in payload
        assert payload["max_completion_tokens"] == max(budget, 4096)
        assert payload["reasoning_effort"] == "low"
        assert requests[0].url.path == "/v1beta/openai/chat/completions"
    finally:
        await service.close()


async def test_other_api_provider_keeps_store_false_and_original_budget(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://api.openai.com/v1")
    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}]})

    service = AIService()
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        await service.chat_api("System", "Test", 64)
        assert payloads[0]["store"] is False
        assert payloads[0]["max_completion_tokens"] == 64
        assert "reasoning_effort" not in payloads[0]
    finally:
        await service.close()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 503])
async def test_provider_error_never_exposes_upstream_body_or_key(status):
    service = AIService()
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=[{"error": {"message": "sensitive-provider-data"}}])))
    try:
        with pytest.raises(AIProviderError) as error:
            await service.chat_api("System", "Test")
        assert "sensitive-provider-data" not in str(error.value)
        assert error.value.status_code == (status if status in {429, 503} else 502)
    finally:
        await service.close()


@pytest.mark.parametrize("path,body,target", [
    ("/api/chat-basic", {"message": "Hi"}, "generate"),
    ("/api/chat-rag", {"question": "Hi"}, "rag"),
    ("/api/embedding-test", {"text": "Hi"}, "embed"),
])
async def test_chat_routes_return_safe_actionable_provider_errors(monkeypatch, path, body, target):
    from app.main import app
    from app.api import chat
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    failure = AsyncMock(side_effect=AIProviderError(503))
    if target == "rag":
        monkeypatch.setattr(chat, "answer_with_rag", failure)
    else:
        monkeypatch.setattr(chat.ollama_service, target, failure)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json=body)
    assert response.status_code == 503
    assert response.json()["code"] == "ai_provider_error"
    assert "sedang sibuk" in response.json()["detail"]
    assert response.headers["Retry-After"] == "30"
