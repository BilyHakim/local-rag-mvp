from unittest.mock import AsyncMock

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

from app.core.config import settings
from app.main import app
from app.services import rag_service
from app.services.rag_errors import RagDependencyError


@pytest.mark.parametrize("question", ["Haloo", "Halo!", "Hi", "Hai bot", "Selamat pagi"])
async def test_greetings_do_not_need_catalog_embedding_database_or_llm(monkeypatch, question):
    from app.api import chat

    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    unavailable = AsyncMock(side_effect=AssertionError("Dependency should not be called"))
    monkeypatch.setattr(chat, "list_chat_models", unavailable)
    monkeypatch.setattr(rag_service.ollama_service, "embed", unavailable)
    monkeypatch.setattr(rag_service.ollama_service, "chat", unavailable)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat-rag", json={"question": question, "model": "selected-model"})
    assert response.status_code == 200
    assert response.json()["status"] == "greeting"
    assert response.json()["sources"] == []
    assert response.json()["answer"].startswith("Halo!")
    unavailable.assert_not_awaited()


@pytest.mark.parametrize("question", ["Halo, apa alamat perusahaan?", "Apa itu sensor?", "Hi bagaimana masa garansi?"])
def test_substantive_questions_are_not_treated_as_greetings(question):
    assert rag_service.greeting_response(question) is None


async def test_database_failure_returns_safe_actionable_error(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(rag_service.ollama_service, "embed", AsyncMock(return_value=[1., 0.]))
    monkeypatch.setattr(rag_service.index_manifest, "versions", lambda: [])
    monkeypatch.setattr(rag_service.index_manifest, "lexical", lambda *args: [])

    def fail(**kwargs):
        raise ResponseHandlingException(httpx.ConnectError("sensitive connection details"))

    monkeypatch.setattr(rag_service.qdrant_service, "search", fail)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat-rag", json={"question": "Apa layanan perusahaan?"})
    assert response.status_code == 503
    assert response.json()["service"] == "qdrant"
    assert "Qdrant" in response.json()["detail"]
    assert "sensitive" not in response.text


async def test_embedding_connection_failure_is_identified(monkeypatch):
    monkeypatch.setattr(rag_service.ollama_service, "embed", AsyncMock(side_effect=httpx.ConnectError("private")))
    with pytest.raises(RagDependencyError) as failure:
        await rag_service.answer_with_rag("Apa layanan perusahaan?")
    assert failure.value.service == "embedding"
    assert "private" not in str(failure.value)
