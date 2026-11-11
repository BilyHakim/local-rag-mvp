import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.core.security import tenant_context
from app.services import auth_service as auth, whatsapp_store as store, whatsapp_service as service

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
hooks = APIRouter()
COOKIE = "wa_settings_session"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Password(Input):
    password: str = Field(min_length=1, max_length=1024)


class SetPassword(Input):
    workspace_password: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=8, max_length=1024)
    old_password: str = Field(default="", max_length=1024)


class ConfigEdit(Input):
    revision: int = Field(ge=0)
    url: str = Field(max_length=500)
    session: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    api_key: str = Field(default="", max_length=512)
    allowed_chats: list[str] = Field(max_length=50)
    enabled: bool = False
    reply_enabled: bool = False
    model: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError("Gunakan URL utama WAHA, misalnya http://waha:3000.")
        try:
            parsed.port
        except ValueError:
            raise ValueError("Port WAHA tidak valid.") from None
        return value

    @field_validator("allowed_chats")
    @classmethod
    def valid_chats(cls, values):
        result = []
        for value in values:
            number = value.strip().removesuffix("@c.us").removeprefix("+")
            if not re.fullmatch(r"[1-9][0-9]{7,14}", number):
                raise ValueError("Isi nomor internasional tanpa spasi, misalnya 6281234567890. Grup belum didukung.")
            result.append(number + "@c.us")
        return list(dict.fromkeys(result))

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("API key tidak boleh memuat baris baru atau karakter kontrol.")
        return value


class Reminder(Input):
    target: str = Field(max_length=50)
    topic: str = Field(min_length=2, max_length=4000)
    due: datetime

    @field_validator("topic")
    @classmethod
    def substantive_topic(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Isi topik atau pertanyaan knowledge.")
        return value

    @field_validator("due")
    @classmethod
    def future(cls, value):
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError("Jadwal harus di masa depan dan menyertakan zona waktu.")
        return value.astimezone(timezone.utc)


async def admin(request: Request):
    principal = await asyncio.to_thread(auth.resolve_session, request.cookies.get(auth.COOKIE_NAME))
    if not principal or principal.get("role") != "admin" or request.headers.get("authorization") or principal != request.state.principal:
        raise HTTPException(403, "Login sebagai admin workspace untuk mengakses pengaturan WhatsApp.")
    return principal


async def gate(request: Request, principal=Depends(admin)):
    if not await asyncio.to_thread(store.unlocked, request.cookies.get(COOKIE), request.cookies.get(auth.COOKIE_NAME)):
        raise HTTPException(423, "Pengaturan WhatsApp terkunci. Masukkan password tambahan.")
    return principal


def public_config(config):
    return {key: value for key, value in config.items() if key != "api_key"} | {"api_key_configured": bool(config["api_key"])}


@router.get("/access")
async def access(request: Request, principal=Depends(admin)):
    remaining = await asyncio.to_thread(store.unlock_remaining, request.cookies.get(COOKIE), request.cookies.get(auth.COOKIE_NAME))
    return {"configured": bool(await asyncio.to_thread(store.config)),
            "unlocked": bool(remaining), "expires_in": remaining}


@router.post("/password")
async def set_password(payload: SetPassword, principal=Depends(admin)):
    try:
        await asyncio.to_thread(store.set_password, principal["username"], payload.workspace_password, payload.password, payload.old_password)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    response = JSONResponse({"message": "Password pengaturan disimpan. Buka kembali dengan password tambahan."})
    response.delete_cookie(COOKIE, path="/api/whatsapp")
    return response


@router.post("/unlock")
async def unlock(payload: Password, request: Request, principal=Depends(admin)):
    token = await asyncio.to_thread(store.unlock, payload.password, request.cookies.get(auth.COOKIE_NAME))
    if not token:
        raise HTTPException(403, "Password pengaturan salah atau belum dibuat.")
    response = JSONResponse({"message": "Pengaturan terbuka selama 15 menit."})
    response.set_cookie(COOKIE, token, max_age=900, httponly=True, samesite="strict", path="/api/whatsapp",
                        secure=settings.APP_ENV != "local" or request.url.scheme == "https")
    return response


@router.post("/lock")
async def lock(request: Request, principal=Depends(admin)):
    await asyncio.to_thread(store.lock, request.cookies.get(COOKIE))
    response = JSONResponse({"message": "Pengaturan dikunci."})
    response.delete_cookie(COOKIE, path="/api/whatsapp")
    return response


@router.get("/settings")
async def get_settings(principal=Depends(gate)):
    return public_config(await asyncio.to_thread(store.config))


@router.put("/settings")
async def save_settings(payload: ConfigEdit, principal=Depends(gate)):
    try:
        return public_config(await asyncio.to_thread(store.save_config, payload.revision, payload.model_dump(exclude={"revision"})))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/connection")
async def connection(principal=Depends(gate)):
    config = await asyncio.to_thread(store.config)
    if not config["api_key"]:
        raise HTTPException(409, "Simpan API key WAHA terlebih dahulu.")
    try:
        result = await service.waha_request(config, "GET", "/api/sessions/" + config["session"])
    except service.WahaError:
        raise HTTPException(502, "WAHA tidak dapat diakses; periksa URL, API key, dan session.") from None
    return {"status": result.get("status", "UNKNOWN") if isinstance(result, dict) else "UNKNOWN"}


@router.get("/jobs")
async def jobs(principal=Depends(gate)):
    return await asyncio.to_thread(store.jobs)


@router.post("/reminders")
async def reminder(payload: Reminder, principal=Depends(gate)):
    config = await asyncio.to_thread(store.config)
    target = payload.target.strip().removeprefix("+").removesuffix("@c.us") + "@c.us"
    if target not in config["allowed_chats"] or not config["enabled"]:
        raise HTTPException(409, "Aktifkan asisten dan pilih nomor yang diizinkan terlebih dahulu.")
    job_id = uuid4().hex
    await asyncio.to_thread(store.enqueue, job_id, "reminder", target, payload.topic.strip(), payload.due.isoformat())
    return {"id": job_id, "status": "pending"}


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, principal=Depends(gate)):
    try:
        await asyncio.to_thread(store.cancel, job_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "cancelled"}


@hooks.post("/hooks/waha/{tenant}")
async def webhook(tenant: str, request: Request):
    if not re.fullmatch(r"[a-z0-9_-]{1,48}", tenant):
        raise HTTPException(404)
    identity = tenant_context.set(tenant)
    try:
        config = await asyncio.to_thread(store.config)
        signature = request.headers.get("X-Webhook-Hmac", "")
        if not config or not re.fullmatch(r"[0-9a-f]{128}", signature) or request.headers.get("X-Webhook-Hmac-Algorithm") != "sha512":
            raise HTTPException(403, "Webhook tidak sah.")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 65536:
                raise HTTPException(413, "Webhook terlalu besar.")
        if not service.verify_webhook(bytes(raw), signature, config):
            raise HTTPException(403, "Webhook tidak sah.")
        try:
            event = json.loads(raw)
            if not isinstance(event, dict):
                raise ValueError()
        except ValueError:
            raise HTTPException(400, "Payload webhook tidak valid.") from None
        queued = await asyncio.to_thread(service.incoming, event, config)
        return {"queued": queued}
    finally:
        tenant_context.reset(identity)
