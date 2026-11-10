import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.core.security import tenant_context
from app.main import app
from app.schemas.workspace import CampaignRequest, SocialDraft
from app.services import campaign_service as campaigns, publishing_service as publishing, workspace_store as store
from app.services.model_service import chat_model_context


@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "")
    monkeypatch.setattr(settings, "IMAGE_MODEL", "")
    monkeypatch.setattr(settings, "IMAGE_API_BASE_URL", "https://images.example.com/v1")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://media.example.com")
    monkeypatch.setattr(settings, "MEDIA_SIGNING_KEY", "s" * 32)
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"instagram_user_id": "123", "instagram_access_token": "test-token"}})
    monkeypatch.setattr(campaigns, "brand_context", AsyncMock(return_value=({"knowledge": [], "profile": {}}, [])))
    token = tenant_context.set("local")
    yield
    tenant_context.reset(token)


def request(**kwargs):
    return CampaignRequest(theme="Edukasi kelautan", first_publish_at=datetime.now(timezone.utc) + timedelta(hours=1),
                           use_knowledge=False, **kwargs)


def slots(campaign):
    return sorted([p for p in store.list_records("post") if p.get("campaign_id") == campaign["id"]], key=lambda p: p["slot_index"])


def text(caption="Periksa sensor aliran sebelum memulai pengukuran agar pembacaan konsisten."):
    return SocialDraft(title="Panduan operasional", caption=caption, image_prompt="Diagram sensor di kapal")


def picture():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "teal").save(buffer, "PNG")
    return buffer.getvalue()


async def test_campaign_atomic_slots_timezone_default_manual_and_model_validation(monkeypatch):
    from app.api import chat
    monkeypatch.setattr(chat, "list_chat_models", AsyncMock(return_value={"models": ["chosen"]}))
    body = request(count=3, interval_hours=48, model="chosen").model_dump(mode="json")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/workspace/social/campaigns", json=body)
        assert response.status_code == 200
        campaign = response.json()
        assert campaign["status"] == "active" and campaign["image_mode"] == "manual"
        posts = slots(campaign)
        assert len(posts) == 3 and all(p["status"] == "queued" for p in posts)
        assert datetime.fromisoformat(posts[1]["scheduled_at"]) - datetime.fromisoformat(posts[0]["scheduled_at"]) == timedelta(hours=48)
        rejected = await client.post("/api/workspace/social/campaigns", json={**body, "model": "unknown"})
        assert rejected.status_code == 422 and len(store.list_records("campaign")) == 1
        other = tenant_context.set("other")
        try:
            assert store.list_records("campaign") == []
            with pytest.raises(KeyError):
                store.get("post", posts[0]["id"])
        finally:
            tenant_context.reset(other)


async def test_generation_model_history_duplicate_retry_and_manual_image_gate(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=2, model="chosen"))
    posts = slots(campaign)
    seen = []

    async def generate(system, data, schema):
        seen.append(data)
        assert chat_model_context.get() == "chosen"
        return text() if len(seen) < 3 else text("Korosi pada lambung kapal perlu dicatat dalam laporan inspeksi berkala. Dokumentasikan lokasi kerusakan untuk merencanakan perawatan saat kapal berada di pelabuhan.")

    monkeypatch.setattr(campaigns.ai_service, "structured", generate)
    await campaigns.generate_slot(posts[0]["id"])
    assert store.get("post", posts[0]["id"])["status"] == "awaiting_image"
    await campaigns.generate_slot(posts[1]["id"])
    assert len(seen) == 3 and seen[1]["previous_posts"]
    assert seen[2]["rejected_similar_captions"]
    assert chat_model_context.get() is None
    generated = store.get("post", posts[0]["id"])
    updated = await publishing.upload_image(generated["id"], generated["revision"], picture())
    assert updated["status"] == "scheduled" and updated["scheduled_at"] == generated["scheduled_at"]


async def test_permanent_duplicate_fails_without_publish(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=2))
    model = AsyncMock(return_value=text())
    monkeypatch.setattr(campaigns.ai_service, "structured", model)
    for post in slots(campaign):
        await campaigns.generate_slot(post["id"])
    assert model.await_count == 4
    assert slots(campaign)[1]["status"] == "failed"
    assert "mirip" in slots(campaign)[1]["error"]


async def test_preuploaded_image_survives_generation_and_atomic_claim(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=1))
    post = slots(campaign)[0]
    uploaded = await publishing.upload_image(post["id"], post["revision"], picture())
    assert uploaded["status"] == "queued"
    model = AsyncMock(return_value=text())
    monkeypatch.setattr(campaigns.ai_service, "structured", model)
    await asyncio.gather(campaigns.generate_slot(post["id"]), campaigns.generate_slot(post["id"]))
    current = store.get("post", post["id"])
    assert model.await_count == 1 and current["status"] == "scheduled"
    assert current["image_id"] == uploaded["image_id"]


async def test_pause_blocks_generation_and_due_publication_then_resume_publishes_once(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=1))
    campaign = await campaigns.change_campaign(campaign["id"], campaign["revision"], "pause")
    model = AsyncMock(return_value=text())
    monkeypatch.setattr(campaigns.ai_service, "structured", model)
    await publishing.scheduler_tick()
    model.assert_not_called()
    campaign = await campaigns.change_campaign(campaign["id"], campaign["revision"], "resume")
    post = slots(campaign)[0]
    await campaigns.generate_slot(post["id"])
    post = store.get("post", post["id"])
    post = await publishing.upload_image(post["id"], post["revision"], picture())
    post = store.update("post", post["id"], post["revision"], post, status="scheduled",
                        scheduled_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    campaign = await campaigns.change_campaign(campaign["id"], campaign["revision"], "pause")
    publisher = AsyncMock(return_value={"external_id": "42", "external_url": None})
    monkeypatch.setattr(publishing, "publish_instagram", publisher)
    await publishing.scheduler_tick()
    publisher.assert_not_called()
    assert store.get("post", post["id"])["status"] == "scheduled"
    campaign = await campaigns.change_campaign(campaign["id"], campaign["revision"], "resume")
    await publishing.scheduler_tick()
    await publishing.scheduler_tick()
    publisher.assert_awaited_once()
    assert store.get("post", post["id"])["status"] == "published"


async def test_campaign_requirements_and_schema_limits(monkeypatch):
    with pytest.raises(ValueError, match="Mode gambar otomatis"):
        await campaigns.create_campaign(request(image_mode="automatic"))
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    with pytest.raises(ValueError, match="scheduler"):
        await campaigns.create_campaign(request())
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "")
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        await campaigns.create_campaign(request())
    assert store.list_records("campaign") == []
    with pytest.raises(ValueError):
        request(count=31)
    with pytest.raises(ValueError):
        CampaignRequest(theme="Tema", first_publish_at="2099-01-01T09:00:00")


async def test_provider_failure_is_fixed_message_and_context_restored(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=1, model="chosen"))
    monkeypatch.setattr(campaigns.ai_service, "structured", AsyncMock(side_effect=RuntimeError("secret-provider-body")))
    await campaigns.generate_slot(slots(campaign)[0]["id"])
    failed = slots(campaign)[0]
    assert failed["status"] == "failed" and "secret" not in failed["error"]
    assert chat_model_context.get() is None


async def test_automatic_image_mode_schedules_after_image_generation(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "test")
    monkeypatch.setattr(settings, "IMAGE_MODEL", "test-image")
    campaign = await campaigns.create_campaign(request(count=1, image_mode="automatic"))
    monkeypatch.setattr(campaigns.ai_service, "structured", AsyncMock(return_value=text()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        "data": [{"b64_json": base64.b64encode(picture()).decode()}],
    }))) as provider:
        monkeypatch.setattr(publishing.ai_service, "_client", provider)
        await campaigns.generate_slot(slots(campaign)[0]["id"])
    post = slots(campaign)[0]
    assert post["status"] == "scheduled" and post["scheduled_at"]
    assert publishing.image_path(post["image_id"]).is_file()


@pytest.mark.parametrize("mode", ["manual", "automatic"])
async def test_campaign_carousel_waits_for_complete_set(monkeypatch, mode):
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "test")
    monkeypatch.setattr(settings, "IMAGE_MODEL", "test-image")
    campaign = await campaigns.create_campaign(request(count=1, image_count=3, image_mode=mode))
    result = text()
    result.image_prompts = ["Cover", "Infographic", "CTA"]
    structured = AsyncMock(return_value=result)
    monkeypatch.setattr(campaigns.ai_service, "structured", structured)
    post = slots(campaign)[0]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        "data": [{"b64_json": base64.b64encode(picture()).decode()}],
    }))) as provider:
        monkeypatch.setattr(publishing.ai_service, "_client", provider)
        await campaigns.generate_slot(post["id"])
    post = slots(campaign)[0]
    assert structured.call_args.args[1]["image_count"] == 3
    if mode == "manual":
        assert post["status"] == "awaiting_image"
        with pytest.raises(ValueError, match="Jumlah gambar"):
            await publishing.upload_images(post["id"], post["revision"], [picture()])
        assert store.get("post", post["id"])["status"] == "awaiting_image"
        post = await publishing.upload_images(post["id"], post["revision"], [picture()] * 3)
    assert post["status"] == "scheduled" and len(post["image_ids"]) == 3
    assert all(publishing.image_path(item).is_file() for item in post["image_ids"])


async def test_campaign_rejects_incomplete_ai_slide_plan(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=1, image_count=3))
    monkeypatch.setattr(campaigns.ai_service, "structured", AsyncMock(return_value=text()))
    await campaigns.generate_slot(slots(campaign)[0]["id"])
    post = slots(campaign)[0]
    assert post["status"] == "failed" and "jumlah slide" in post["error"]
    assert campaigns.ai_service.structured.await_count == 3


async def test_ambiguous_campaign_publish_is_not_retried(monkeypatch):
    campaign = await campaigns.create_campaign(request(count=1))
    monkeypatch.setattr(campaigns.ai_service, "structured", AsyncMock(return_value=text()))
    post = slots(campaign)[0]
    await campaigns.generate_slot(post["id"])
    post = store.get("post", post["id"])
    post = await publishing.upload_image(post["id"], post["revision"], picture())
    post = store.update("post", post["id"], post["revision"], post, status="scheduled",
                        scheduled_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    publisher = AsyncMock(side_effect=publishing.PublishUncertain())
    monkeypatch.setattr(publishing, "publish_instagram", publisher)
    await publishing.scheduler_tick()
    await publishing.scheduler_tick()
    publisher.assert_awaited_once()
    assert store.get("post", post["id"])["status"] == "uncertain"


async def test_paused_campaign_cannot_claim_publication_atomically():
    campaign = await campaigns.create_campaign(request(count=1))
    post = slots(campaign)[0]
    post = store.update("post", post["id"], post["revision"], post, status="scheduled", scheduled_at=post["scheduled_at"])
    await campaigns.change_campaign(campaign["id"], campaign["revision"], "pause")
    with pytest.raises(ValueError, match="dijeda"):
        store.update("post", post["id"], post["revision"], post, status="publishing", allowed={"scheduled"})
    assert store.get("post", post["id"])["status"] == "scheduled"


async def test_recovery_marks_interrupted_generation_failed_but_keeps_manual_image_wait():
    campaign = await campaigns.create_campaign(request(count=3))
    posts = slots(campaign)
    for post, status, pending in zip(posts, ["generating", "awaiting_image", "awaiting_image"], [False, True, False]):
        store.update("post", post["id"], post["revision"], dict(post, image_generation_pending=pending), status=status)
    with store.connection() as db:
        db.execute("UPDATE records SET updated_at=? WHERE kind='post'", ((datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat(),))
    store.recover_stale_jobs()
    assert [p["status"] for p in slots(campaign)] == ["failed", "failed", "awaiting_image"]


async def test_slow_generation_does_not_block_publication_ticks_and_shutdown_cancels_it(monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()
    two_ticks = asyncio.Event()
    ticks = 0

    async def generate():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def tick():
        nonlocal ticks
        ticks += 1
        if ticks >= 2:
            two_ticks.set()

    monkeypatch.setattr(campaigns, "generate_pending_slots", generate)
    monkeypatch.setattr(publishing, "scheduler_tick", tick)
    monkeypatch.setattr(settings, "SCHEDULER_INTERVAL_SECONDS", 0.01)
    task = asyncio.create_task(publishing.scheduler_loop())
    try:
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(two_ticks.wait(), 1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert stopped.is_set()
