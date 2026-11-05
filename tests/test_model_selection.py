import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.services.ai_service import ai_service
from app.services.model_service import chat_model_context, list_chat_models


async def test_catalog_filters_incompatible_endpoints_and_keeps_credentials_server_side(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "api")
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://api.commandcode.ai/provider/v1")
    monkeypatch.setattr(settings, "AI_API_KEY", "server-only-secret")

    def respond(request):
        assert request.url.path == "/provider/v1/models"
        assert request.headers["Authorization"] == "Bearer server-only-secret"
        return httpx.Response(200, json={"data": [
            {"id": "text-model", "supported_endpoints": ["/v1/chat/completions"]},
            {"id": "claude", "supported_endpoints": ["/v1/messages"]},
            {"id": "decision", "supported_endpoints": ["/v1/systemone"]},
            {"id": "text-model", "supported_endpoints": ["/v1/chat/completions"]},
        ]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(ai_service, "_client", client)
        catalog = await list_chat_models()
    assert catalog["models"] == ["text-model"]
    assert "server-only-secret" not in json.dumps(catalog)


async def test_concurrent_rag_requests_keep_model_isolated_and_restore_default(monkeypatch):
    from app.api import chat

    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(settings, "AI_CHAT_MODEL", "default-model")

    async def catalog():
        return {"models": ["model-a", "model-b"]}

    arrived = 0
    ready = asyncio.Event()

    async def rag(question, top_k):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), 2)
        answer = await ai_service.chat_api("system", question)
        return {"answer": answer, "sources": []}

    def respond(request):
        model = json.loads(request.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": model}}]})

    monkeypatch.setattr(chat, "list_chat_models", catalog)
    monkeypatch.setattr(chat, "answer_with_rag", rag)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.post("/api/chat-rag", json={"question": "Pertanyaan", "model": model})
                for model in ("model-a", "model-b")
            ])
            assert [response.json()["answer"] for response in responses] == ["model-a", "model-b"]
            rejected = await client.post("/api/chat-rag", json={"question": "Test", "model": "claude"})
            assert rejected.status_code == 422
        assert await ai_service.chat_api("system", "test") == "default-model"
    assert chat_model_context.get() is None
    assert settings.AI_CHAT_MODEL == "default-model"


async def test_ollama_catalog(monkeypatch):
    from app.services.ollama_service import ollama_service

    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "local:3b"}]}),
    )) as client:
        monkeypatch.setattr(ollama_service, "_client", client)
        assert (await list_chat_models())["models"] == ["local:3b"]


async def test_failed_rag_restores_model_context(monkeypatch):
    from app.api import chat
    from app.schemas.chat import ChatRagRequest
    from app.services.ai_service import AIProviderError

    async def catalog():
        return {"models": ["selected"]}

    async def fail(**kwargs):
        assert chat_model_context.get() == "selected"
        raise AIProviderError(503)

    monkeypatch.setattr(chat, "list_chat_models", catalog)
    monkeypatch.setattr(chat, "answer_with_rag", fail)
    with pytest.raises(AIProviderError):
        await chat.chat_rag(ChatRagRequest(question="Test", model="selected"))
    assert chat_model_context.get() is None
