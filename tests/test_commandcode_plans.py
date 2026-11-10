import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.services.ai_service import ai_service, AIModelAccessError
from app.services.model_service import list_chat_models, chat_model_context


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AI_PROVIDER", "api")
    monkeypatch.setattr(settings, "AI_API_BASE_URL", "https://api.commandcode.ai/provider/v1")
    monkeypatch.setattr(settings, "AI_API_KEY", "private-key")
    monkeypatch.setattr(settings, "AI_CHAT_MODEL", "gpt-6-sol")
    monkeypatch.setattr(settings, "COMMANDCODE_PLAN", "goat")
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    monkeypatch.setattr(app, "middleware_stack", None)


def catalog_response(request):
    assert request.method == "GET"
    return httpx.Response(200, json={"data": [
        {"id": "gpt-6-sol", "supported_endpoints": ["/chat/completions"]},
        {"id": "gpt-6.1-terra", "supported_endpoints": ["/chat/completions"]},
        {"id": "gpt-6-luna", "supported_endpoints": ["/chat/completions"]},
        {"id": "google/gemini-3.8-flash", "supported_endpoints": ["/chat/completions"]},
        {"id": "deepseek/deepseek-v4.1-flash", "supported_endpoints": ["/messages"]},
        {"id": "unlisted-new-model", "supported_endpoints": ["/chat/completions"]},
    ]})


async def test_goat_catalog_uses_exact_ids_endpoint_filter_and_allowed_default(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.MockTransport(catalog_response)) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        catalog = await list_chat_models()
    assert catalog["plan"] == "goat"
    assert catalog["models"] == ["google/gemini-3.8-flash", "gpt-6-luna"]
    assert catalog["default_model"] in catalog["models"]
    assert "private-key" not in json.dumps(catalog)
    assert settings.AI_CHAT_MODEL == "gpt-6-sol"


@pytest.mark.parametrize("base,plan", [("https://api.commandcode.ai/provider/v1", "catalog"), ("https://other.example/v1", "goat")])
async def test_catalog_mode_and_other_providers_are_not_plan_filtered(monkeypatch, base, plan):
    monkeypatch.setattr(settings, "AI_API_BASE_URL", base)
    monkeypatch.setattr(settings, "COMMANDCODE_PLAN", plan)
    async with httpx.AsyncClient(transport=httpx.MockTransport(catalog_response)) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        catalog = await list_chat_models()
    assert "gpt-6-sol" in catalog["models"]
    assert catalog["plan"] == "catalog"


async def test_premium_selection_rejected_before_generating_and_default_saved_correctly(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.MockTransport(catalog_response)) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        model = AsyncMock(return_value="Siap")
        monkeypatch.setattr(ai_service, "chat_api", model)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            denied = await client.post("/api/assistant/messages", json={"message": "Halo", "model": "gpt-6-sol"})
            assert denied.status_code == 422
            model.assert_not_awaited()
            selected = []
            async def answer(*args, **kwargs):
                selected.append(chat_model_context.get())
                return "Siap"
            model.side_effect = answer
            result = await client.post("/api/assistant/messages", json={"message": "Halo"})
            assert result.status_code == 200
            assert result.json()["model"] == selected[0] == "google/gemini-3.8-flash"
    assert chat_model_context.get() is None


async def test_stored_or_direct_premium_model_cannot_bypass_plan(monkeypatch):
    provider = AsyncMock()
    monkeypatch.setattr(ai_service, "api_post", provider)
    token = chat_model_context.set("gpt-6.1-terra")
    try:
        with pytest.raises(AIModelAccessError) as error:
            await ai_service.chat_api("System", "Halo")
        assert error.value.status_code == 422 and "GOAT" in error.value.detail
    finally:
        chat_model_context.reset(token)
    with pytest.raises(AIModelAccessError):
        await ai_service.chat_api("System", "Halo")
    provider.assert_not_awaited()


async def test_no_matching_models_cannot_fall_back_to_premium(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"id": "gpt-6-sol"}]}))) as provider:
        monkeypatch.setattr(ai_service, "_client", provider)
        catalog = await list_chat_models()
        assert catalog["models"] == [] and catalog["default_model"] == ""
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            result = await client.post("/api/assistant/messages", json={"message": "Halo"})
        assert result.status_code == 422
