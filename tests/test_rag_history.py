from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import rag_history
from app.core.config import settings
from app.main import app
from app.schemas.chat import ChatRagResponse
from app.services import auth_service as auth

HEADERS = {"X-Requested-With": "workspace"}


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_INITIAL_PASSWORD", "")
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(app, "middleware_stack", None)
    result = ChatRagResponse(answer="Garansi 6 bulan.", sources=[{"id": "source", "score": .9, "text": "Garansi 6 bulan.", "filename": "garansi.docx"}],
                             citations=[{"source_id": "source", "evidence_text": "Garansi 6 bulan.", "filename": "garansi.docx"}])
    mock = AsyncMock(return_value=result)
    monkeypatch.setattr(rag_history, "chat_rag", mock)
    return mock


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        yield client


async def login(client, username="admin", password="admin123"):
    response = await client.post("/api/auth/login", headers=HEADERS, json={"username": username, "password": password})
    assert response.status_code == 200


async def send(client, **kwargs):
    return await client.post("/api/rag-history/messages", headers=HEADERS, json={"question": "Berapa garansi?", "top_k": 5, **kwargs})


async def test_rag_history_saves_turns_sources_and_survives_relogin(client, environment):
    response = await send(client, model="selected-model")
    assert response.status_code == 200
    saved = response.json()["conversation"]
    await client.post("/api/auth/logout", headers=HEADERS)
    await login(client)
    records = (await client.get("/api/rag-history/conversations")).json()
    assert records[0]["id"] == saved["id"] and "messages" not in records[0]
    record = (await client.get("/api/rag-history/conversations/" + saved["id"])).json()
    assert record["model"] == "selected-model" and record["top_k"] == 5
    assert record["messages"][0]["content"] == "Berapa garansi?"
    assert record["messages"][1]["sources"][0]["filename"] == "garansi.docx"
    assert record["messages"][1]["citations"][0]["evidence_text"] == "Garansi 6 bulan."
    environment.assert_awaited_once()


@pytest.mark.parametrize("tenant,role", [("local", "reader"), ("local", "admin"), ("another", "admin")])
async def test_other_accounts_cannot_read_continue_or_delete_history(client, tenant, role):
    saved = (await send(client)).json()["conversation"]
    with auth.connection() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?)", ("other", auth.password_hash("other-password"), tenant, role))
    await login(client, "other", "other-password")
    assert (await client.get("/api/rag-history/conversations")).json() == []
    path = "/api/rag-history/conversations/" + saved["id"]
    assert (await client.get(path)).status_code == 404
    assert (await client.delete(path + "?revision=1", headers=HEADERS)).status_code == 404
    assert (await send(client, conversation_id=saved["id"], revision=1)).status_code == 404
    own = (await send(client)).json()["conversation"]
    await login(client)
    assert (await client.get("/api/rag-history/conversations/" + own["id"])).status_code == 404


async def test_turn_revisions_conflicts_and_deletion(client, environment):
    saved = (await send(client)).json()["conversation"]
    assert (await send(client, conversation_id=saved["id"], revision=1)).status_code == 200
    assert (await send(client, conversation_id=saved["id"], revision=1)).status_code == 409
    assert environment.await_count == 2
    path = "/api/rag-history/conversations/" + saved["id"]
    assert len((await client.get(path)).json()["messages"]) == 4
    assert (await client.delete(path + "?revision=1", headers=HEADERS)).status_code == 409
    assert (await client.delete(path + "?revision=2", headers=HEADERS)).status_code == 200
    assert (await client.get(path)).status_code == 404


async def test_api_keys_and_disabled_features_cannot_access_private_history(client, monkeypatch):
    saved = (await send(client)).json()["conversation"]
    key = "k" * 40
    monkeypatch.setattr(settings, "API_KEYS", {key: {"tenant": "local", "role": "admin"}})
    assert (await client.get("/api/rag-history/conversations", headers={"Authorization": "Bearer " + key})).status_code == 403
    with auth.connection() as db:
        db.execute("INSERT INTO account_profiles VALUES (?,?,?)", ("admin", 1, '{"enabled_features":[]}'))
    assert (await client.get("/api/rag-history/conversations")).status_code == 403
    assert (await client.get("/api/rag-history/conversations/" + saved["id"])).status_code == 403


@pytest.mark.parametrize("data", [{"question": "  "}, {"conversation_id": "a" * 32}, {"revision": 1}, {"username": "other"}])
async def test_invalid_turn_identity_is_not_accepted(client, data, environment):
    assert (await send(client, **data)).status_code == 422
    environment.assert_not_awaited()


async def test_generation_error_does_not_persist_or_overwrite_history(client, environment):
    saved = (await send(client)).json()["conversation"]
    environment.side_effect = httpx.ConnectError("provider unavailable")
    assert (await send(client, conversation_id=saved["id"], revision=1)).status_code == 502
    record = (await client.get("/api/rag-history/conversations/" + saved["id"])).json()
    assert record["revision"] == 1 and len(record["messages"]) == 2
