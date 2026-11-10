import asyncio
import hashlib
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from app.api.chat import select_model
from app.api.workspace import WorkspaceRoute
from app.core.config import settings
from app.services import workspace_store as store
from app.services.ai_service import ai_service
from app.services.model_service import chat_model_context


router = APIRouter(prefix="/assistant", route_class=WorkspaceRoute)


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_turn(self):
        self.message = self.message.strip()
        if not self.message or bool(self.conversation_id) != (self.revision is not None):
            raise ValueError("Isi pesan dan versi percakapan harus valid")
        return self


def conversation_kind(request):
    principal = request.state.principal
    identity = principal.get("username") or request.headers.get("authorization", "local")
    return "assistant_" + hashlib.sha256(identity.encode()).hexdigest()


@router.get("/conversations")
async def conversations(request: Request):
    records = await asyncio.to_thread(store.list_records, conversation_kind(request), 10000)
    return [{k: item[k] for k in ("id", "revision", "title", "updated_at", "model")} for item in records]


@router.get("/conversations/{record_id}")
async def conversation(record_id: str, request: Request):
    return await asyncio.to_thread(store.get, conversation_kind(request), record_id)


@router.delete("/conversations/{record_id}")
async def delete_conversation(record_id: str, revision: int, request: Request):
    kind = conversation_kind(request)
    await asyncio.to_thread(store.get, kind, record_id)
    await asyncio.to_thread(store.delete, kind, record_id, revision)
    return {"message": "Percakapan dihapus."}


@router.post("/messages")
async def message(payload: MessageRequest, request: Request):
    if settings.AI_PROVIDER != "api" or urlsplit(settings.AI_API_BASE_URL).hostname != "api.commandcode.ai" or not settings.AI_API_KEY:
        raise HTTPException(503, "Ruang Chat memerlukan konfigurasi provider CommandCode pada server.")
    kind = conversation_kind(request)
    current = await asyncio.to_thread(store.get, kind, payload.conversation_id) if payload.conversation_id else None
    if current and current["revision"] != payload.revision:
        raise ValueError("Percakapan berubah. Buka ulang sebelum mengirim pesan.")
    turns = current["messages"] if current else []
    if len(turns) >= 200:
        raise ValueError("Percakapan mencapai 100 balasan. Mulai percakapan baru untuk melanjutkan.")
    context = []
    size = len(payload.message)
    for index in range(len(turns) - 2, max(-1, len(turns) - 41), -2):
        pair = turns[index:index + 2]
        size += sum(len(turn["content"]) for turn in pair)
        if size > 60000:
            break
        context[0:0] = [{"role": turn["role"], "content": turn["content"]} for turn in pair]
    token = await select_model(payload.model)
    try:
        answer = await ai_service.chat_api(
            "Anda asisten percakapan umum bernama Ruang Chat. Bantu pengguna berdiskusi, menulis, belajar, "
            "menganalisis dan membuat kode. Jawab dalam bahasa pengguna, jelas dan sesuai kebutuhan. "
            "Gunakan konteks percakapan yang diberikan. Jujur jika tidak tahu atau konteks tidak tersedia. "
            "Anda tidak memiliki akses browsing, file, knowledge perusahaan atau alat eksekusi. "
            "Jangan mengklaim melakukan pencarian atau menjalankan tindakan. Gunakan Markdown bila membantu.",
            payload.message, max_tokens=8192, history=context)
    finally:
        chat_model_context.reset(token)
    data = {"title": current["title"] if current else payload.message[:70],
            "model": payload.model or settings.AI_CHAT_MODEL,
            "messages": turns + [{"role": "user", "content": payload.message}, {"role": "assistant", "content": answer}],
            "context_limited": len(context) < len(turns)}
    if current:
        return await asyncio.to_thread(store.update, kind, current["id"], payload.revision, data)
    return await asyncio.to_thread(store.create, kind, data)
