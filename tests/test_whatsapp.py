import hashlib
import asyncio
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.core.config import settings
from app.core.security import tenant_context
from app.main import app
from app.services import auth_service as auth, whatsapp_store as store, whatsapp_service as service
from app.services.rag_service import FALLBACK_ANSWER

HEADERS = {"X-Requested-With": "workspace"}
PHONE = "6281234567890@c.us"


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_INITIAL_PASSWORD", "")
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(app, "middleware_stack", None)
    identity = tenant_context.set("local")
    yield
    tenant_context.reset(identity)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/auth/login", headers=HEADERS, json={"username": "admin", "password": "admin123"})
        yield client


async def ready(client):
    response = await client.post("/api/whatsapp/password", headers=HEADERS, json={"workspace_password": "admin123", "password": "separate-password"})
    assert response.status_code == 200
    response = await client.post("/api/whatsapp/unlock", headers=HEADERS, json={"password": "separate-password"})
    assert response.status_code == 200
    data = {"revision": 0, "url": "http://waha:3000", "session": "default", "api_key": "secret-api-key", "allowed_chats": [PHONE], "enabled": True, "reply_enabled": True, "model": ""}
    response = await client.put("/api/whatsapp/settings", headers=HEADERS, json=data)
    assert response.status_code == 200
    return response.json()


async def test_gate_requires_different_password_and_main_password(client):
    assert (await client.get("/api/whatsapp/settings")).status_code == 423
    for main, password in [("wrong", "separate-password"), ("admin123", "admin123")]:
        response = await client.post("/api/whatsapp/password", headers=HEADERS, json={"workspace_password": main, "password": password})
        assert response.status_code == 409
    config = await ready(client)
    assert "api_key" not in config and config["api_key_configured"]
    assert "secret-api-key" not in (await client.get("/api/whatsapp/settings")).text
    with store.connection() as db:
        hashed = db.execute("SELECT password_hash FROM wa_settings").fetchone()[0]
    assert hashed.startswith("scrypt$") and "separate-password" not in hashed
    await client.post("/api/whatsapp/lock", headers=HEADERS)
    assert (await client.get("/api/whatsapp/jobs")).status_code == 423


async def test_unlock_is_bound_to_main_session_and_expires(client):
    await ready(client)
    with store.connection() as db:
        db.execute("UPDATE wa_unlocks SET expires=?", (int(time.time()) + 40,))
    access = (await client.get("/api/whatsapp/access")).json()
    assert access["unlocked"] and 0 < access["expires_in"] <= 40
    await client.post("/api/auth/login", headers=HEADERS, json={"username": "admin", "password": "admin123"})
    assert (await client.get("/api/whatsapp/settings")).status_code == 423
    await client.post("/api/whatsapp/unlock", headers=HEADERS, json={"password": "separate-password"})
    with store.connection() as db:
        db.execute("UPDATE wa_unlocks SET expires=0")
    assert (await client.get("/api/whatsapp/settings")).status_code == 423


async def test_password_rotation_revokes_unlocks_and_requires_old(client):
    await ready(client)
    data = {"workspace_password": "admin123", "password": "new-separate-password", "old_password": "wrong"}
    assert (await client.post("/api/whatsapp/password", headers=HEADERS, json=data)).status_code == 409
    data["old_password"] = "separate-password"
    assert (await client.post("/api/whatsapp/password", headers=HEADERS, json=data)).status_code == 200
    assert (await client.get("/api/whatsapp/settings")).status_code == 423


async def test_gate_rejects_api_keys_readers_and_csrf(client, monkeypatch):
    await ready(client)
    key = "a" * 40
    monkeypatch.setattr(settings, "API_KEYS", {key: {"tenant": "local", "role": "admin"}})
    assert (await client.get("/api/whatsapp/settings", headers={"Authorization": "Bearer " + key})).status_code == 403
    assert (await client.post("/api/whatsapp/unlock", json={"password": "separate-password"})).status_code == 403
    with auth.connection() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?)", ("reader", auth.password_hash("reader-pass"), "local", "reader"))
    await client.post("/api/auth/login", headers=HEADERS, json={"username": "reader", "password": "reader-pass"})
    assert (await client.get("/api/whatsapp/access")).status_code == 403


async def test_unlock_rate_limited(client):
    for _ in range(10):
        assert (await client.post("/api/whatsapp/unlock", headers=HEADERS, json={"password": "wrong"})).status_code == 403
    assert (await client.post("/api/whatsapp/unlock", headers=HEADERS, json={"password": "wrong"})).status_code == 429


async def test_config_validation_revision_and_tenant_isolation(client):
    config = await ready(client)
    data = {key: value for key, value in config.items() if key not in {"webhook_secret", "api_key_configured"}}
    data["api_key"] = ""
    saved = await client.put("/api/whatsapp/settings", headers=HEADERS, json=data)
    assert saved.status_code == 200 and store.config()["api_key"] == "secret-api-key"
    assert (await client.put("/api/whatsapp/settings", headers=HEADERS, json=data)).status_code == 409
    data["url"] = "http://user:pass@waha:3000/path?key=bad"
    assert (await client.put("/api/whatsapp/settings", headers=HEADERS, json=data)).status_code == 422
    identity = tenant_context.set("another")
    try:
        assert store.config() is None and store.jobs() == []
    finally:
        tenant_context.reset(identity)


async def test_reminder_schedule_allowlist_and_cancel(client):
    await ready(client)
    data = {"target": PHONE, "topic": "Berapa garansi lampu?", "due": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    result = await client.post("/api/whatsapp/reminders", headers=HEADERS, json=data)
    assert result.status_code == 200
    job_id = result.json()["id"]
    assert (await client.post(f"/api/whatsapp/jobs/{job_id}/cancel", headers=HEADERS)).status_code == 200
    assert store.jobs()[0]["status"] == "cancelled"
    data["target"] = "6299999999999"
    assert (await client.post("/api/whatsapp/reminders", headers=HEADERS, json=data)).status_code == 409
    data["due"] = "2020-01-01T00:00:00"
    assert (await client.post("/api/whatsapp/reminders", headers=HEADERS, json=data)).status_code == 422


def event(**changes):
    return {"event": "message", "session": "default", "payload": {"id": "msg-1", "from": PHONE, "fromMe": False, "body": "Berapa garansi?", "timestamp": time.time(), **changes}}


async def test_webhook_signature_dedup_and_cross_tenant(client):
    config = await ready(client)
    raw = json.dumps(event()).encode()
    signature = hmac.new(config["webhook_secret"].encode(), raw, hashlib.sha512).hexdigest()
    headers = {"Content-Type": "application/json", "X-Webhook-Hmac": signature, "X-Webhook-Hmac-Algorithm": "sha512"}
    assert (await client.post("/hooks/waha/local", content=raw)).status_code == 403
    assert (await client.post("/hooks/waha/another", content=raw, headers=headers)).status_code == 403
    assert (await client.post("/hooks/waha/local", content=raw + b" ", headers=headers)).status_code == 403
    assert (await client.post("/hooks/waha/local", content=raw, headers=headers)).json()["queued"]
    assert not (await client.post("/hooks/waha/local", content=raw, headers=headers)).json()["queued"]
    assert len(store.jobs()) == 1


@pytest.mark.parametrize("changes", [{"fromMe": True}, {"from": "6299999999999@c.us"}, {"from": "123@g.us"}, {"body": ""}, {"timestamp": 0}, {"timestamp": float("nan")}, {"id": None}])
async def test_incoming_ignores_unapproved_or_own_messages(client, changes):
    await ready(client)
    assert service.incoming(event(**changes), store.config()) is False
    assert store.jobs() == []


async def test_job_uses_rag_and_never_sends_twice(client, monkeypatch):
    await ready(client)
    from app.api import chat
    monkeypatch.setattr(chat, "select_model", AsyncMock(return_value=None))
    rag = AsyncMock(return_value={"status": "answered", "answer": "Garansi 6 bulan.", "citations": [{"filename": "garansi.docx"}]})
    send = AsyncMock(return_value={"id": "accepted"})
    monkeypatch.setattr(service, "answer_with_rag", rag)
    monkeypatch.setattr(service, "waha_request", send)
    store.enqueue("reminder", "reminder", PHONE, "Berapa garansi?", store.workspace.now_iso())
    job = store.due_jobs()[0]
    await service.process_job(job)
    await service.process_job(job)
    rag.assert_awaited_once_with("Berapa garansi?")
    send.assert_awaited_once()
    payload = send.await_args.args[3]
    assert payload["chatId"] == PHONE and "Garansi 6 bulan." in payload["text"] and "garansi.docx" in payload["text"]
    assert store.jobs()[0]["status"] == "sent"


@pytest.mark.parametrize("kind,status,expected", [("reminder", "insufficient_evidence", "skipped"), ("reply", "insufficient_evidence", "sent")])
async def test_missing_knowledge_skips_reminder_but_replies_honestly(client, monkeypatch, kind, status, expected):
    await ready(client)
    from app.api import chat
    monkeypatch.setattr(chat, "select_model", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "answer_with_rag", AsyncMock(return_value={"status": status, "answer": FALLBACK_ANSWER, "citations": []}))
    send = AsyncMock(return_value={"id": "accepted"})
    monkeypatch.setattr(service, "waha_request", send)
    store.enqueue("job", kind, PHONE, "Pertanyaan tidak diketahui?", store.workspace.now_iso())
    await service.process_job(store.due_jobs()[0])
    assert store.jobs()[0]["status"] == expected
    assert send.await_count == (kind == "reply")


@pytest.mark.parametrize("invalid_receipt", [False, True])
async def test_uncertain_send_and_crash_are_never_automatically_retried(client, monkeypatch, invalid_receipt):
    await ready(client)
    from app.api import chat
    monkeypatch.setattr(chat, "select_model", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "answer_with_rag", AsyncMock(return_value={"status": "answered", "answer": "Fakta.", "citations": []}))
    monkeypatch.setattr(service, "waha_request", AsyncMock(return_value={}) if invalid_receipt else AsyncMock(side_effect=service.WahaError(uncertain=True)))
    store.enqueue("job", "reminder", PHONE, "Apa fakta?", store.workspace.now_iso())
    await service.process_job(store.due_jobs()[0])
    assert store.jobs()[0]["status"] == "uncertain" and store.jobs()[0]["answer"]
    store.enqueue("crash", "reply", PHONE, "Apa fakta?", store.workspace.now_iso())
    store.finish("crash", "sending", answer="Already sending")
    store.recover()
    assert all(row["status"] == "uncertain" for row in store.jobs())
    assert store.due_jobs() == []


@pytest.mark.parametrize("status,uncertain", [(401, False), (500, True), (302, False)])
async def test_waha_transport_rejects_errors_without_leaking_keys(monkeypatch, status, uncertain):
    original = httpx.AsyncClient

    def respond(request):
        assert request.headers["X-Api-Key"] == "private-key"
        assert request.url == "http://waha:3000/api/sendText"
        return httpx.Response(status, json={"detail": "private-provider-detail"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    with pytest.raises(service.WahaError) as failure:
        await service.waha_request({"url": "http://waha:3000", "api_key": "private-key"}, "POST", "/api/sendText", {"text": "test"})
    assert failure.value.uncertain == uncertain
    assert "private" not in str(failure.value)


async def test_worker_retries_startup_recovery_before_processing(monkeypatch):
    recover = Mock(side_effect=[OSError("temporary storage failure"), None])
    due = Mock(return_value=[])
    monkeypatch.setattr(store, "recover", recover)
    monkeypatch.setattr(store, "due_jobs", due)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError]))
    with pytest.raises(asyncio.CancelledError):
        await service.scheduler_loop()
    assert recover.call_count == 2
    due.assert_called_once()


async def test_paused_tenant_jobs_do_not_block_other_tenants(client):
    await ready(client)
    for i in range(21):
        store.enqueue(str(i), "reminder", PHONE, "Paused reminder", store.workspace.now_iso())
    with store.connection() as db:
        row = db.execute("SELECT * FROM wa_settings WHERE tenant='local'").fetchone()
        db.execute("INSERT INTO wa_settings VALUES (?,?,?,?)", ("another", row['password_hash'], row['revision'], row['data']))
        db.execute("UPDATE wa_settings SET data=json_set(data,'$.enabled',0) WHERE tenant='local'")
    identity = tenant_context.set("another")
    try:
        store.enqueue("active", "reminder", PHONE, "Active reminder", store.workspace.now_iso())
    finally:
        tenant_context.reset(identity)
    assert [row['id'] for row in store.due_jobs()] == ['active']
