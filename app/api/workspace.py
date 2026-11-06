import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from app.core.config import settings
from app.schemas.workspace import (BrandProfile, AuditRequest, GenerateRequest, PostEdit,
                                   RevisionRequest, ScheduleRequest, ResolveRequest, ManualPostRequest)
from app.services import workspace_store as store
from app.services.specialist_service import audit_url, generate_social
from app.api.chat import select_model
from app.services.model_service import chat_model_context
from app.schemas.workspace import CampaignRequest
from app.services import campaign_service as campaigns
from app.services.publishing_service import (connections, generate_image, image_path, publish_post,
                                   validate_publishable, validate_signature, upload_image, instagram_connection)


class WorkspaceRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except KeyError as exc:
                raise HTTPException(404, "Data tidak ditemukan") from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            except (httpx.HTTPError, OSError, TimeoutError) as exc:
                raise HTTPException(502, "Layanan eksternal gagal diakses") from exc
        return handler


router = APIRouter(prefix="/workspace", route_class=WorkspaceRoute)
media_router = APIRouter()


@router.get("/status")
async def workspace_status():
    config = connections()
    return {"text_provider": settings.AI_PROVIDER,
            "text_model": settings.AI_CHAT_MODEL if settings.AI_PROVIDER == "api" else settings.OLLAMA_CHAT_MODEL,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "image_configured": bool(settings.IMAGE_API_KEY and settings.IMAGE_MODEL),
            "instagram_configured": bool(config.get("instagram_user_id") and config.get("instagram_access_token")),
            "wordpress_configured": bool(config.get("wordpress_url") and config.get("wordpress_username") and config.get("wordpress_app_password")),
            "public_media_configured": bool(settings.PUBLIC_BASE_URL and len(settings.MEDIA_SIGNING_KEY) >= 32),
            "scheduler_enabled": settings.SCHEDULER_ENABLED}


@router.get("/profile", response_model=BrandProfile)
async def profile():
    try:
        return await asyncio.to_thread(store.get, "profile", "brand")
    except KeyError:
        return BrandProfile()


@router.get("/instagram/connection")
async def check_instagram_connection():
    return await instagram_connection()


@router.post("/social/posts")
async def manual_post(payload: ManualPostRequest):
    return await asyncio.to_thread(store.create, "post", dict(payload.model_dump(),
                                  image_prompt="", hashtags=[], notes="", history=[], sources=[], warnings=[]))


@router.put("/profile", response_model=BrandProfile)
async def save_profile(payload: BrandProfile):
    return await asyncio.to_thread(store.set_profile, payload.model_dump())


@router.post("/seo/audits")
async def create_audit(payload: AuditRequest):
    return await audit_url(payload)


@router.get("/seo/audits")
async def audits():
    return await asyncio.to_thread(store.list_records, "audit")


@router.get("/seo/audits/{record_id}")
async def audit(record_id: str):
    return await asyncio.to_thread(store.get, "audit", record_id)


@router.post("/social/generate")
async def social_generate(payload: GenerateRequest):
    token = await select_model(payload.model)
    try:
        return await generate_social(payload)
    finally:
        chat_model_context.reset(token)


@router.get("/social/posts")
async def posts():
    return await asyncio.to_thread(store.list_records, "post")


@router.get("/social/campaigns")
async def list_campaigns():
    return await campaigns.list_campaigns()


@router.post("/social/campaigns")
async def create_campaign(payload: CampaignRequest):
    token = await select_model(payload.model)
    try:
        return await campaigns.create_campaign(payload)
    finally:
        chat_model_context.reset(token)


@router.post("/social/campaigns/{record_id}/{action}")
async def campaign_action(record_id: str, action: str, payload: RevisionRequest):
    if action not in {"pause", "resume"}:
        raise HTTPException(404, "Aksi tidak ditemukan")
    return await campaigns.change_campaign(record_id, payload.revision, action)


@router.get("/social/posts/{record_id}")
async def post(record_id: str):
    return await asyncio.to_thread(store.get, "post", record_id)


@router.put("/social/posts/{record_id}")
async def edit_post(record_id: str, payload: PostEdit):
    current = await asyncio.to_thread(store.get, "post", record_id)
    data = dict(current, **payload.model_dump(exclude={"revision"}), error=None)
    # Text edits keep the existing preview image, but invalidate approval and schedule.
    return await asyncio.to_thread(store.update, "post", record_id, payload.revision, data,
                                   status="awaiting_image" if current["status"] == "awaiting_image" else "draft",
                                   scheduled_at=current["scheduled_at"] if current["status"] == "awaiting_image" else None,
                                   allowed={"draft", "approved", "scheduled", "failed", "awaiting_image"})


@router.post("/social/posts/{record_id}/image")
async def create_image(record_id: str, payload: RevisionRequest):
    return await generate_image(record_id, payload.revision)


@router.get("/social/posts/{record_id}/image")
async def preview_image(record_id: str):
    current = await asyncio.to_thread(store.get, "post", record_id)
    path = image_path(current.get("image_id"))
    if not path.is_file():
        raise HTTPException(404, "Gambar belum tersedia")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/social/posts/{record_id}/image-upload")
async def upload_post_image(record_id: str, revision: int = Form(..., ge=1), file: UploadFile = File(...)):
    try:
        raw = await file.read(min(settings.MAX_UPLOAD_BYTES, 10 * 1024 * 1024) + 1)
        return await upload_image(record_id, revision, raw)
    finally:
        await file.close()


@router.post("/social/posts/{record_id}/approve")
async def approve_post(record_id: str, payload: RevisionRequest):
    current = await asyncio.to_thread(store.get, "post", record_id)
    # Approval can be given before credentials are configured, but requires final material.
    if current["channel"] == "instagram" and not current.get("image_id"):
        raise ValueError("Buat gambar sebelum menyetujui posting Instagram")
    return await asyncio.to_thread(store.update, "post", record_id, payload.revision, dict(current, error=None),
                                   status="approved", allowed={"draft", "failed"})


@router.post("/social/posts/{record_id}/schedule")
async def schedule_post(record_id: str, payload: ScheduleRequest):
    if not settings.SCHEDULER_ENABLED:
        raise ValueError("Aktifkan SCHEDULER_ENABLED pada server sebelum menjadwalkan")
    current = await asyncio.to_thread(store.get, "post", record_id)
    validate_publishable(current)
    return await asyncio.to_thread(store.update, "post", record_id, payload.revision, current,
                                   status="scheduled", scheduled_at=payload.scheduled_at.isoformat(), allowed={"approved"})


@router.post("/social/posts/{record_id}/cancel")
async def cancel_schedule(record_id: str, payload: RevisionRequest):
    current = await asyncio.to_thread(store.get, "post", record_id)
    return await asyncio.to_thread(store.update, "post", record_id, payload.revision, current,
                                   status="draft", allowed={"scheduled", "approved"})


@router.post("/social/posts/{record_id}/publish")
async def publish(record_id: str, payload: RevisionRequest):
    return await publish_post(record_id, payload.revision)


@router.post("/social/posts/{record_id}/resolve")
async def resolve(record_id: str, payload: ResolveRequest):
    current = await asyncio.to_thread(store.get, "post", record_id)
    if payload.outcome == "published" and not payload.external_id.strip():
        raise ValueError("ID posting diperlukan untuk mencatat hasil yang sudah diterbitkan")
    return await asyncio.to_thread(store.update, "post", record_id, payload.revision,
                                   dict(current, error=None, external_id=payload.external_id or None,
                                        external_url=payload.external_url or None),
                                   status="published" if payload.outcome == "published" else "draft", allowed={"uncertain"})


@media_router.get("/media/{tenant}/{image_id}", include_in_schema=False)
async def signed_media(tenant: str, image_id: str, expires: int, signature: str):
    if not validate_signature(tenant, image_id, expires, signature):
        raise HTTPException(403, "Tautan media tidak valid atau kedaluwarsa")
    try:
        path = image_path(image_id, tenant)
    except ValueError as exc:
        raise HTTPException(404, "Media tidak ditemukan") from exc
    if not path.is_file():
        raise HTTPException(404, "Media tidak ditemukan")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
