import asyncio
import base64
import io
import json
import socket
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.core.security import tenant_context
from app.main import app
from app.schemas.workspace import GenerateRequest, SocialDraft, ScheduleRequest
from app.services import workspace_store as store, publishing_service as publishing
from app.services import specialist_service as specialists
from app.services.ai_service import AIService
from app.services.ollama_service import OllamaService
from app.services.public_web import public_target


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {})
    token = tenant_context.set("local")
    yield tmp_path
    tenant_context.reset(token)


def draft(channel="website"):
    return store.create("post", {"title": "Ocean awareness", "caption": "Learn about oceans.", "image_prompt": "Blue ocean",
                                 "hashtags": ["ocean"], "channel": channel, "notes": "", "history": [], "sources": [], "warnings": []})


async def client_request(method, path, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_tenant_profile_and_post_boundary():
    post = draft()
    store.set_profile({"name": "Alpha"})
    token = tenant_context.set("beta")
    try:
        assert store.list_records("post") == []
        with pytest.raises(KeyError):
            store.get("post", post["id"])
        with pytest.raises(KeyError):
            store.get("profile", "brand")
        store.set_profile({"name": "Beta"})
    finally:
        tenant_context.reset(token)
    assert store.get("profile", "brand")["name"] == "Alpha"


def test_edit_invalidates_approval_and_stale_revision_cannot_overwrite():
    post = draft()
    approved = store.update("post", post["id"], 1, post, status="approved", allowed={"draft"})
    scheduled = store.update("post", post["id"], 2, approved, status="scheduled", scheduled_at=store.now_iso(), allowed={"approved"})
    edited = store.update("post", post["id"], 3, dict(scheduled, caption="New caption"), allowed={"scheduled"})
    assert edited["status"] == "draft" and edited["scheduled_at"] is None
    with pytest.raises(ValueError):
        store.update("post", post["id"], 3, scheduled, status="approved")
    assert store.get("post", post["id"])["caption"] == "New caption"


async def test_single_claim_under_concurrent_publish(monkeypatch):
    post = draft()
    post = store.update("post", post["id"], 1, post, status="approved")
    monkeypatch.setattr(publishing, "validate_publishable", lambda p: None)
    publish = AsyncMock(return_value={"external_id": "42", "external_url": "https://example.com/post"})
    monkeypatch.setattr(publishing, "publish_wordpress", publish)
    results = await asyncio.gather(publishing.publish_post(post["id"], 2), publishing.publish_post(post["id"], 2), return_exceptions=True)
    assert publish.await_count == 1
    assert any(isinstance(result, ValueError) for result in results)
    assert store.get("post", post["id"])["status"] == "published"


async def test_ambiguous_publish_is_not_retried_by_scheduler(monkeypatch):
    post = draft()
    post = store.update("post", post["id"], 1, post, status="scheduled", scheduled_at=store.now_iso())
    monkeypatch.setattr(publishing, "validate_publishable", lambda p: None)
    publish = AsyncMock(side_effect=publishing.PublishUncertain())
    monkeypatch.setattr(publishing, "publish_wordpress", publish)
    await publishing.scheduler_tick()
    await publishing.scheduler_tick()
    assert publish.await_count == 1
    assert store.get("post", post["id"])["status"] == "uncertain"


async def test_scheduler_restores_tenant_and_only_publishes_due_approved_material(monkeypatch):
    draft()  # Unapproved draft must not publish.
    future = draft()
    store.update("post", future["id"], 1, future, status="scheduled", scheduled_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    token = tenant_context.set("beta")
    post = draft()
    store.update("post", post["id"], 1, post, status="scheduled", scheduled_at=store.now_iso())
    tenant_context.reset(token)
    seen = []

    async def publish(p):
        seen.append((tenant_context.get(), p["id"]))
        return {"external_id": "42"}

    monkeypatch.setattr(publishing, "validate_publishable", lambda p: None)
    monkeypatch.setattr(publishing, "publish_wordpress", publish)
    await publishing.scheduler_tick()
    assert seen == [("beta", post["id"])]
    assert tenant_context.get() == "local"


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1"])
async def test_audit_blocks_private_dns_targets(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))])
    with pytest.raises(ValueError):
        await public_target("https://example.com/")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:secret@example.com", "http://example.com:8080"])
async def test_audit_blocks_unsafe_urls(url):
    with pytest.raises(ValueError):
        await public_target(url)


def test_observations_are_derived_from_html():
    result = specialists.inspect_page({"url": "https://example.com", "status": 200, "headers": {},
                                       "body": b'<html><head><title>Test</title><meta name="robots" content="noindex"></head><body><h1>Heading</h1><img src="a.jpg"><img src="b.jpg" alt=""><script>ignore this</script><a href="/about">About</a></body></html>'})
    assert result["title"] == "Test" and result["h1"] == ["Heading"]
    assert result["missing_alt"] == 1 and result["internal_links"] == 1
    assert "ignore this" not in result["text_excerpt"]
    assert any("noindex" in f["issue"] for f in result["findings"])


async def test_audit_preserves_evidence_if_model_unavailable(monkeypatch):
    from app.schemas.workspace import AuditRequest
    monkeypatch.setattr(specialists, "fetch_public", AsyncMock(return_value={"url": "https://example.com", "status": 200,
                                                                          "headers": {"content-type": "text/html"}, "body": b"<html><h1>Hello</h1></html>"}))
    monkeypatch.setattr(specialists.ai_service, "structured", AsyncMock(side_effect=RuntimeError("offline")))
    audit = await specialists.audit_url(AuditRequest(url="https://example.com", use_knowledge=False))
    assert audit["observations"]["findings"] and audit["analysis"] is None
    assert store.get("audit", audit["id"])["analysis_error"]


async def test_social_chat_revises_same_post_and_resets_approval(monkeypatch):
    model = AsyncMock(side_effect=[SocialDraft(title="First", caption="Caption", image_prompt="Ocean"),
                                   SocialDraft(title="Revised", caption="New caption", image_prompt="Blue ocean")])
    monkeypatch.setattr(specialists.ai_service, "structured", model)
    post = await specialists.generate_social(GenerateRequest(brief="Make a post", use_knowledge=False))
    post = store.update("post", post["id"], 1, post, status="approved")
    revised = await specialists.generate_social(GenerateRequest(brief="Make it shorter", use_knowledge=False,
                                                                post_id=post["id"], revision=2))
    assert revised["id"] == post["id"] and revised["status"] == "draft"
    assert len(revised["history"]) == 2
    assert revised["title"] == "Revised"


async def test_social_model_selection_creation_revision_and_default(monkeypatch):
    from app.api import chat
    from app.services.model_service import chat_model_context

    monkeypatch.setattr(chat, "list_chat_models", AsyncMock(return_value={"models": ["model-a", "model-b"]}))
    seen = []

    async def structured(*args):
        seen.append(chat_model_context.get())
        await asyncio.sleep(0)
        assert chat_model_context.get() == seen[-1]
        return SocialDraft(title="Title", caption="Caption", image_prompt="Ocean")

    monkeypatch.setattr(specialists.ai_service, "structured", structured)
    body = {"brief": "Create a post", "use_knowledge": False, "model": "model-a"}
    created = await client_request("POST", "/api/workspace/social/generate", json=body)
    assert created.status_code == 200
    post = created.json()
    revised = await client_request("POST", "/api/workspace/social/generate", json={
        **body, "model": "model-b", "post_id": post["id"], "revision": post["revision"],
    })
    assert revised.status_code == 200
    assert revised.json()["id"] == post["id"]
    default = await client_request("POST", "/api/workspace/social/generate", json={**body, "model": None})
    assert default.status_code == 200
    assert seen == ["model-a", "model-b", None]
    rejected = await client_request("POST", "/api/workspace/social/generate", json={**body, "model": "unknown"})
    assert rejected.status_code == 422
    assert len(seen) == 3
    assert chat_model_context.get() is None


async def test_social_provider_failure_restores_model_context(monkeypatch):
    from app.api import chat, workspace
    from app.services.ai_service import AIProviderError
    from app.services.model_service import chat_model_context

    monkeypatch.setattr(chat, "list_chat_models", AsyncMock(return_value={"models": ["chosen"]}))

    async def fail(payload):
        assert chat_model_context.get() == "chosen"
        raise AIProviderError(503)

    monkeypatch.setattr(workspace, "generate_social", fail)
    with pytest.raises(AIProviderError):
        await workspace.social_generate(GenerateRequest(brief="Make a post", model="chosen"))
    assert chat_model_context.get() is None


def test_schedule_rejects_naive_and_past_times():
    with pytest.raises(ValueError):
        ScheduleRequest(revision=1, scheduled_at=datetime.now())
    with pytest.raises(ValueError):
        ScheduleRequest(revision=1, scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1))
    value = ScheduleRequest(revision=1, scheduled_at="2099-01-01T09:00:00+07:00")
    assert value.scheduled_at.hour == 2


async def test_reader_cannot_publish_or_read_admin_workspace(monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", {"r" * 32: {"tenant": "alpha", "role": "reader"}})
    headers = {"Authorization": "Bearer " + "r" * 32}
    assert (await client_request("GET", "/api/workspace/profile", headers=headers)).status_code == 403
    assert (await client_request("POST", "/api/workspace/social/posts/unknown/publish", json={"revision": 1}, headers=headers)).status_code == 403


async def test_api_profile_does_not_expose_secrets(monkeypatch):
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"instagram_user_id": "42", "instagram_access_token": "secret"}})
    response = await client_request("PUT", "/api/workspace/profile", json={"name": "Our company", "description": "Ocean protection"})
    assert response.status_code == 200 and response.json()["name"] == "Our company"
    response = await client_request("GET", "/api/workspace/status")
    assert response.status_code == 200 and response.json()["instagram_configured"]
    assert "secret" not in response.text


async def test_api_edit_is_stale_safe_and_cannot_set_status():
    post = draft()
    url = f"/api/workspace/social/posts/{post['id']}"
    response = await client_request("PUT", url, json={"revision": 1, "title": "Edited", "caption": "new", "status": "published"})
    assert response.status_code == 200 and response.json()["status"] == "draft"
    response = await client_request("PUT", url, json={"revision": 1, "title": "Stale", "caption": "stale"})
    assert response.status_code == 409
    assert store.get("post", post["id"])["title"] == "Edited"


async def test_image_generation_persists_jpeg_and_signed_media_is_scoped(monkeypatch):
    post = draft("instagram")
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, "PNG")
    monkeypatch.setattr(settings, "IMAGE_API_KEY", "image-secret")
    monkeypatch.setattr(settings, "IMAGE_MODEL", "test-image")
    monkeypatch.setattr(settings, "IMAGE_API_BASE_URL", "https://images.example.com/v1")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://workspace.example.com")
    monkeypatch.setattr(settings, "MEDIA_SIGNING_KEY", "s" * 32)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]})))
    monkeypatch.setattr(publishing.ai_service, "_client", client)
    try:
        result = await publishing.generate_image(post["id"], 1)
    finally:
        await client.aclose()
    assert result["status"] == "draft" and result["image_id"]
    assert publishing.image_path(result["image_id"]).read_bytes().startswith(b"\xff\xd8")
    signed = publishing.public_image_url(result["image_id"])
    response = await client_request("GET", signed.replace("https://workspace.example.com", ""))
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    response = await client_request("GET", signed.replace("https://workspace.example.com", "").replace("/local/", "/beta/"))
    assert response.status_code == 403


async def test_manual_post_and_uploaded_image_require_no_ai(monkeypatch):
    monkeypatch.setattr(publishing.ai_service, "api_post", AsyncMock(side_effect=AssertionError("No AI calls")))
    response = await client_request("POST", "/api/workspace/social/posts", json={"channel": "instagram", "caption": "Tes integrasi"})
    post = response.json()
    post = store.update("post", post["id"], post["revision"], post, status="scheduled", scheduled_at=store.now_iso())
    path = f"/api/workspace/social/posts/{post['id']}/image-upload"
    image = io.BytesIO()
    Image.new("RGB", (64, 64), "teal").save(image, "PNG")
    response = await client_request("POST", path, data={"revision": post["revision"]}, files={"file": ("test.png", image.getvalue(), "image/png")})
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "draft" and updated["scheduled_at"] is None
    assert publishing.image_path(updated["image_id"]).read_bytes().startswith(b"\xff\xd8")
    response = await client_request("POST", path, data={"revision": post["revision"]}, files={"file": ("test.png", image.getvalue(), "image/png")})
    assert response.status_code == 409
    assert len(list(publishing.image_path(updated["image_id"]).parent.glob("*.jpg"))) == 1


@pytest.mark.parametrize("content", [b"not an image", b""])
async def test_upload_rejects_invalid_content(content):
    post = draft("instagram")
    response = await client_request("POST", f"/api/workspace/social/posts/{post['id']}/image-upload",
                                    data={"revision": 1}, files={"file": ("test.jpg", content, "image/jpeg")})
    assert response.status_code == 409
    assert store.get("post", post["id"])["revision"] == 1


async def test_upload_rejects_other_tenant_and_bad_aspect_ratio():
    post = draft("instagram")
    image = io.BytesIO()
    Image.new("RGB", (10, 100), "blue").save(image, "PNG")
    with pytest.raises(ValueError, match="Rasio"):
        await publishing.upload_image(post["id"], 1, image.getvalue())
    token = tenant_context.set("other")
    try:
        with pytest.raises(KeyError):
            await publishing.upload_image(post["id"], 1, image.getvalue())
    finally:
        tenant_context.reset(token)


async def test_image_upload_over_256kb_passes_middleware():
    import random
    image = io.BytesIO()
    Image.frombytes("RGB", (512, 512), random.Random(7).randbytes(512 * 512 * 3)).save(image, "PNG")
    assert len(image.getvalue()) > 256 * 1024
    post = draft("instagram")
    response = await client_request("POST", f"/api/workspace/social/posts/{post['id']}/image-upload",
                                    data={"revision": 1}, files={"file": ("large.png", image.getvalue(), "image/png")})
    assert response.status_code == 200
    assert response.json()["image_id"]


async def test_image_multipart_limit_does_not_expand_json_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    post = draft("instagram")
    response = await client_request("POST", f"/api/workspace/social/posts/{post['id']}/image-upload",
                                    data={"revision": 1}, files={"file": ("large.png", b"x" * (1024 * 1024 + 2048), "image/png")})
    assert response.status_code == 413
    response = await client_request("POST", "/api/workspace/social/posts", content=b"x" * (256 * 1024 + 1))
    assert response.status_code == 413


async def test_instagram_connection_reads_identity_without_publishing(monkeypatch):
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"instagram_user_id": "123", "instagram_access_token": "secret", "instagram_login_mode": "unified"}})
    original = httpx.AsyncClient

    def respond(request):
        assert request.method == "GET" and request.url.host == "graph.facebook.com"
        assert request.url.params["fields"] == "id,username"
        return httpx.Response(200, json={"id": "123", "username": "test-account"})

    monkeypatch.setattr(publishing.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    assert await publishing.instagram_connection() == {"id": "123", "username": "test-account", "connected": True}


async def test_api_provider_is_used_for_rag_text_and_embeddings(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "api")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "api")
    monkeypatch.setattr(settings, "AI_CHAT_MODEL", "test-text")
    monkeypatch.setattr(settings, "AI_EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setattr(settings, "AI_API_KEY", "secret")
    from app.services.ai_service import ai_service
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0., 1.]}, {"index": 0, "embedding": [1., 0.]}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "API answer"}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(ai_service, "_client", client)
    try:
        service = OllamaService()
        assert await service.chat("system", "question") == "API answer"
        assert await service.embed_many(["a", "b"]) == [[1., 0.], [0., 1.]]
        assert requests[0].headers["Authorization"] == "Bearer secret"
        assert json.loads(requests[0].content)["model"] == "test-text"
    finally:
        await client.aclose()


@pytest.mark.parametrize("mode,host", [("instagram", "graph.instagram.com"), ("unified", "graph.facebook.com")])
async def test_instagram_container_then_publish_and_permalink(monkeypatch, mode, host):
    post = draft("instagram")
    post = store.update("post", post["id"], 1, post, status="publishing")
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"instagram_user_id": "123", "instagram_access_token": "secret", "instagram_login_mode": mode}})
    monkeypatch.setattr(publishing, "public_image_url", lambda image_id: "https://example.com/image.jpg")
    post["image_id"] = "a" * 32
    calls = []

    def respond(request):
        assert request.url.host == host
        calls.append(request.url.path)
        if request.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "456"})
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "789"})
        if request.url.path.endswith("/789"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/example/"})

    original = httpx.AsyncClient
    monkeypatch.setattr(publishing.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    result = await publishing.publish_instagram(post)
    assert result["external_id"] == "456"
    assert calls[0].endswith("/media") and calls[2].endswith("/media_publish")
    assert store.get("post", post["id"])["instagram_container_id"] == "789"


async def test_wordpress_escapes_content_and_publishes_saved_draft(monkeypatch):
    post = draft()
    post = store.update("post", post["id"], 1, dict(post, caption="<script>bad()</script>"), status="publishing")
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"wordpress_url": "https://example.com", "wordpress_username": "user", "wordpress_app_password": "secret"}})
    calls = []

    def respond(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": 123, "status": "publish", "link": "https://example.com/post"})

    original = httpx.AsyncClient
    monkeypatch.setattr(publishing.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    result = await publishing.publish_wordpress(post)
    assert calls[0][1]["status"] == "draft" and "&lt;script&gt;" in calls[0][1]["content"]
    assert calls[1] == ("/wp-json/wp/v2/posts/123", {"status": "publish"})
    assert result["external_id"] == "123"


async def test_public_fetch_pins_ip_and_validates_redirect_before_request(monkeypatch):
    import app.services.public_web as web
    calls = []

    def resolve(host, port, **kwargs):
        ip = "127.0.0.1" if host == "private.example" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://private.example/admin"})

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    with pytest.raises(ValueError):
        await web.fetch_public("https://public.example/page")
    assert len(calls) == 1
    assert calls[0].url.host == "93.184.216.34"
    assert calls[0].headers["host"] == "public.example"
    assert calls[0].extensions["sni_hostname"] == "public.example"


async def test_public_fetch_bounds_response_size(monkeypatch):
    import app.services.public_web as web
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 100)), **kw))
    with pytest.raises(ValueError, match="ukuran"):
        await web.fetch_public("https://example.com", max_bytes=50)


async def test_http_draft_approval_schedule_publish_lifecycle(monkeypatch):
    monkeypatch.setattr(specialists.ai_service, "structured", AsyncMock(return_value=SocialDraft(title="Article", caption="Content", image_prompt="Ocean")))
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLISHING_CONNECTIONS", {"local": {"wordpress_url": "https://example.com", "wordpress_username": "publisher", "wordpress_app_password": "test-only"}})
    monkeypatch.setattr(publishing, "validate_publishable", lambda p: None)
    publisher = AsyncMock(return_value={"external_id": "42", "external_url": "https://example.com/article"})
    monkeypatch.setattr(publishing, "publish_wordpress", publisher)
    response = await client_request("POST", "/api/workspace/social/generate", json={"brief": "Write an educational article", "channel": "website", "use_knowledge": False})
    assert response.status_code == 200
    post = response.json()
    path = f"/api/workspace/social/posts/{post['id']}"
    assert (await client_request("POST", path + "/publish", json={"revision": 1})).status_code == 409
    response = await client_request("POST", path + "/approve", json={"revision": 1})
    assert response.json()["status"] == "approved"
    response = await client_request("POST", path + "/schedule", json={"revision": 2, "scheduled_at": "2099-01-01T09:00:00+07:00"})
    assert response.status_code == 200 and response.json()["scheduled_at"].endswith("02:00:00+00:00")
    assert publisher.await_count == 0
    post = response.json()
    store.update("post", post["id"], post["revision"], post, status="scheduled", scheduled_at=store.now_iso())
    await publishing.scheduler_tick()
    response = await client_request("GET", path)
    assert response.json()["status"] == "published" and response.json()["external_id"] == "42"
    assert publisher.await_count == 1


async def test_uncertain_api_requires_reconciliation_before_retry():
    post = draft()
    post = store.update("post", post["id"], 1, post, status="uncertain")
    path = f"/api/workspace/social/posts/{post['id']}"
    response = await client_request("POST", path + "/approve", json={"revision": post["revision"]})
    assert response.status_code == 409
    response = await client_request("POST", path + "/resolve", json={"revision": post["revision"], "outcome": "published"})
    assert response.status_code == 409
    response = await client_request("POST", path + "/resolve", json={"revision": post["revision"], "outcome": "published", "external_id": "42", "external_url": "https://example.com/article"})
    assert response.status_code == 200 and response.json()["status"] == "published"


async def test_scheduler_rechecks_jobs_rescheduled_after_due_snapshot(monkeypatch):
    post = draft()
    post = store.update("post", post["id"], 1, post, status="scheduled", scheduled_at=store.now_iso())
    original = store.due_jobs

    def snapshot_then_reschedule():
        jobs = original()
        store.update("post", post["id"], post["revision"], post, status="scheduled",
                     scheduled_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
        return jobs

    monkeypatch.setattr(store, "due_jobs", snapshot_then_reschedule)
    publisher = AsyncMock()
    monkeypatch.setattr(publishing, "publish_wordpress", publisher)
    await publishing.scheduler_tick()
    assert publisher.await_count == 0
    assert store.get("post", post["id"])["status"] == "scheduled"
