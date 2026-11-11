import asyncio
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ConfigDict, Field, model_validator

from app.api.chat import chat_rag
from app.api.workspace import WorkspaceRoute
from app.core.security import tenant_context
from app.schemas.chat import ChatRagRequest
from app.services import auth_service as auth, workspace_store as store

router = APIRouter(prefix="/api/rag-history", route_class=WorkspaceRoute, tags=["rag-history"])


class MessageRequest(ChatRagRequest):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_turn(self):
        self.question = self.question.strip()
        if len(self.question) < 2 or bool(self.conversation_id) != (self.revision is not None):
            raise ValueError("Pertanyaan dan versi percakapan harus valid.")
        return self


async def private_kind(request: Request):
    principal = await asyncio.to_thread(auth.resolve_session, request.cookies.get(auth.COOKIE_NAME))
    if not principal or request.headers.get("authorization") or principal != request.state.principal:
        raise HTTPException(403, "Login dengan akun workspace untuk mengakses riwayat RAG pribadi.")
    return "rag_" + hashlib.sha256(principal["username"].encode()).hexdigest()


def summaries(kind):
    with store.connection() as db:
        rows = db.execute("SELECT id,revision,updated_at,json_extract(data,'$.title') AS title,json_extract(data,'$.model') AS model FROM records WHERE tenant=? AND kind=? ORDER BY updated_at DESC LIMIT 10000",
                          (tenant_context.get(), kind)).fetchall()
    return [dict(row) for row in rows]


@router.get("/conversations")
async def conversations(kind=Depends(private_kind)):
    return await asyncio.to_thread(summaries, kind)


@router.get("/conversations/{record_id}")
async def conversation(record_id: str, kind=Depends(private_kind)):
    return await asyncio.to_thread(store.get, kind, record_id)


@router.delete("/conversations/{record_id}")
async def delete_conversation(record_id: str, revision: int = Query(ge=1), kind=Depends(private_kind)):
    await asyncio.to_thread(store.get, kind, record_id)
    await asyncio.to_thread(store.delete, kind, record_id, revision)
    return {"message": "Percakapan RAG dihapus."}


@router.post("/messages")
async def message(payload: MessageRequest, kind=Depends(private_kind)):
    current = await asyncio.to_thread(store.get, kind, payload.conversation_id) if payload.conversation_id else None
    if current and current["revision"] != payload.revision:
        raise ValueError("Percakapan berubah. Buka ulang sebelum mengirim pertanyaan.")
    turns = current["messages"] if current else []
    if len(turns) >= 200:
        raise ValueError("Percakapan mencapai 100 jawaban. Mulai percakapan baru untuk melanjutkan.")
    result = await chat_rag(ChatRagRequest(question=payload.question, model=payload.model, top_k=payload.top_k))
    answer = result.model_dump()
    data = {"title": current["title"] if current else payload.question[:70],
            "model": payload.model,
            "top_k": payload.top_k,
            "messages": turns + [{"role": "user", "content": payload.question},
                                 {"role": "assistant", "content": answer["answer"], "sources": answer["sources"],
                                  "citations": answer["citations"], "status": answer["status"]}]}
    if current:
        saved = await asyncio.to_thread(store.update, kind, current["id"], payload.revision, data)
    else:
        saved = await asyncio.to_thread(store.create, kind, data)
    return {**answer, "conversation": {"id": saved["id"], "revision": saved["revision"]}}
