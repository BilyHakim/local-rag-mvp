import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.services.ai_service import AIProviderError, ai_service
from app.services import workspace_store as store
from app.services.model_service import chat_model_context


@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "AI_PROVIDER", "api")
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://api.commandcode.ai/provider/v1")
    monkeypatch.setattr(settings, "AI_API_KEY", "secret")
    monkeypatch.setattr(settings, "AI_CHAT_MODEL", "default-model")
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "API_KEYS", {
        "alice": {"username": "alice", "tenant": "team", "role": "reader"},
        "bob": {"username": "bob", "tenant": "team", "role": "admin"},
        "other": {"username": "alice", "tenant": "other", "role": "reader"}})
    monkeypatch.setattr(app, "middleware_stack", None)


async def call(method, path, user="alice", **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, "/api/assistant" + path, headers={"Authorization": "Bearer " + user}, **kwargs)


async def test_commandcode_multiturn_and_private_history(monkeypatch):
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "Hai, Bily."}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        first = await call("POST", "/messages", json={"message": "Nama saya Bily"})
        assert first.status_code == 200
        post = first.json()
        second = await call("POST", "/messages", json={"message": "Siapa nama saya?", "conversation_id": post["id"], "revision": post["revision"]})
        assert second.status_code == 200 and len(second.json()["messages"]) == 4
        assert calls[1]["messages"][1:3] == post["messages"]
        assert calls[1]["messages"][-1]["content"] == "Siapa nama saya?"
        assert calls[1]["store"] is False
        assert chat_model_context.get() is None
        assert (await call("GET", "/conversations")).json()[0]["title"] == "Nama saya Bily"
        for user in ("bob", "other"):
            assert (await call("GET", "/conversations", user=user)).json() == []
            assert (await call("GET", "/conversations/" + post["id"], user=user)).status_code == 404
            assert (await call("DELETE", "/conversations/" + post["id"] + "?revision=2", user=user)).status_code == 404
        assert (await call("DELETE", "/conversations/" + post["id"] + "?revision=1")).status_code == 409
        assert (await call("DELETE", "/conversations/" + post["id"] + "?revision=2")).status_code == 200
        assert (await call("GET", "/conversations")).json() == []


async def test_failed_provider_preserves_conversation_and_context(monkeypatch):
    mock = AsyncMock(return_value="Jawaban pertama")
    monkeypatch.setattr(ai_service, "chat_api", mock)
    post = (await call("POST", "/messages", json={"message": "Halo"})).json()
    mock.side_effect = AIProviderError(429)
    response = await call("POST", "/messages", json={"message": "Lanjut", "conversation_id": post["id"], "revision": 1})
    assert response.status_code == 429 and "secret" not in response.text
    assert (await call("GET", "/conversations/" + post["id"])).json()["messages"] == post["messages"]
    assert chat_model_context.get() is None
    mock.reset_mock()
    response = await call("POST", "/messages", json={"message": "Lanjut", "conversation_id": post["id"], "revision": 99})
    assert response.status_code == 409
    mock.assert_not_awaited()


@pytest.mark.parametrize("body", [{"message": " "}, {"message": "x" * 12001}, {"message": "Halo", "conversation_id": "a" * 32}, {"message": "Halo", "revision": 1}])
async def test_message_validation(body):
    assert (await call("POST", "/messages", json=body)).status_code == 422


async def test_explicit_model_and_context_limit(monkeypatch):
    from app.api import chat
    monkeypatch.setattr(chat, "list_chat_models", AsyncMock(return_value={"models": ["chosen"]}))
    seen = []
    async def answer(*args, **kwargs):
        seen.append((chat_model_context.get(), kwargs.get("history")))
        return "Balasan"
    monkeypatch.setattr(ai_service, "chat_api", answer)
    post = (await call("POST", "/messages", json={"message": "Mulai", "model": "chosen"})).json()
    assert seen[0][0] == "chosen"
    assert (await call("POST", "/messages", json={"message": "Halo", "model": "unknown"})).status_code == 422
    from app.core.security import tenant_context
    token = tenant_context.set("team")
    try:
        import hashlib
        kind = "assistant_" + hashlib.sha256(b"alice").hexdigest()
        turns = [{"role": role, "content": str(i)} for i in range(25) for role in ("user", "assistant")]
        post = store.update(kind, post["id"], 1, dict(post, messages=turns))
    finally:
        tenant_context.reset(token)
    response = await call("POST", "/messages", json={"message": "Lanjut", "conversation_id": post["id"], "revision": post["revision"]})
    assert response.status_code == 200 and response.json()["context_limited"]
    assert len(seen[-1][1]) == 40 and seen[-1][1][0]["role"] == "user"


async def test_only_configured_commandcode_and_authenticated_users(monkeypatch):
    assert (await call("GET", "/conversations", user="invalid")).status_code == 401
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://other.example/v1")
    assert (await call("POST", "/messages", json={"message": "Halo"})).status_code == 503
