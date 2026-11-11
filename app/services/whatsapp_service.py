import asyncio
import hashlib
import hmac
import logging
import math
import time

import httpx

from app.core.security import tenant_context
from app.services import whatsapp_store as store
from app.services.rag_service import answer_with_rag
from app.services.model_service import chat_model_context


class WahaError(Exception):
    def __init__(self, uncertain=False):
        self.uncertain = uncertain


async def waha_request(config, method, path, data=None):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5), trust_env=False) as client:
            response = await client.request(method, config["url"] + path, headers={"X-Api-Key": config["api_key"]}, json=data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise WahaError(uncertain=method == "POST" and exc.response.status_code >= 500) from None
    except (httpx.RequestError, ValueError):
        raise WahaError(uncertain=method == "POST") from None


def verify_webhook(raw, signature, config):
    expected = hmac.new(config["webhook_secret"].encode(), raw, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


def incoming(event, config):
    payload = event.get("payload")
    if (not config["enabled"] or not config["reply_enabled"] or event.get("event") != "message"
            or event.get("session") != config["session"] or not isinstance(payload, dict)):
        return False
    target, body, msg_id = payload.get("from"), payload.get("body"), payload.get("id")
    timestamp = payload.get("timestamp")
    if (payload.get("fromMe") is not False or target not in config["allowed_chats"]
            or not isinstance(body, str) or not 2 <= len(body.strip()) <= 4000
            or not isinstance(msg_id, str) or not 1 <= len(msg_id) <= 500
            or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or abs(time.time() - timestamp) > 300):
        return False
    job_id = hashlib.sha256((config["session"] + ":" + msg_id).encode()).hexdigest()
    return store.enqueue(job_id, "reply", target, body.strip(), store.workspace.now_iso())


async def process_job(job):
    config = await asyncio.to_thread(store.config)
    if not config or not config["enabled"]:
        return
    if not await asyncio.to_thread(store.claim, job["id"]):
        return
    if job["target"] not in config["allowed_chats"] or (job["kind"] == "reply" and not config["reply_enabled"]):
        await asyncio.to_thread(store.finish, job["id"], "cancelled", error="Nomor atau balasan otomatis sudah dinonaktifkan.")
        return
    sending = False
    token = None
    try:
        from app.api.chat import select_model
        token = await select_model(config["model"] or None)
        result = await answer_with_rag(job["topic"])
        if job["kind"] == "reminder" and result["status"] != "answered":
            await asyncio.to_thread(store.finish, job["id"], "skipped", error="Knowledge belum menyediakan bukti yang cukup untuk reminder ini.")
            return
        answer = result["answer"]
        if job["kind"] == "reminder":
            answer = "Pengingat\n\n" + answer
        filenames = list(dict.fromkeys(c["filename"] for c in result["citations"] if c.get("filename")))
        if filenames:
            answer += "\n\nSumber: " + ", ".join(filenames)
        # Persist the send boundary: a crash here must never trigger automatic resend.
        await asyncio.to_thread(store.finish, job["id"], "sending", answer=answer)
        sending = True
        receipt = await waha_request(config, "POST", "/api/sendText", {"session": config["session"], "chatId": job["target"], "text": answer})
        if not isinstance(receipt, dict) or not receipt.get("id"):
            raise WahaError(uncertain=True)
        await asyncio.to_thread(store.finish, job["id"], "sent", answer=answer)
    except WahaError as exc:
        await asyncio.to_thread(store.finish, job["id"], "uncertain" if exc.uncertain else "failed",
                                error="Status pengiriman belum pasti; periksa WhatsApp." if exc.uncertain else "WAHA menolak pengiriman; periksa koneksi dan session.")
    except asyncio.CancelledError:
        raise
    except Exception:
        await asyncio.to_thread(store.finish, job["id"], "uncertain" if sending else "failed", error="Pengiriman terputus; periksa WhatsApp." if sending else "Penyusunan reminder gagal; periksa model dan knowledge.")
        logging.getLogger("whatsapp").error("whatsapp_job_failed")
    finally:
        if token is not None:
            chat_model_context.reset(token)


async def scheduler_loop():
    recovered = False
    while True:
        try:
            if not recovered:
                await asyncio.to_thread(store.recover)
                recovered = True
            for job in await asyncio.to_thread(store.due_jobs):
                identity = tenant_context.set(job["tenant"])
                try:
                    await process_job(job)
                finally:
                    tenant_context.reset(identity)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger("whatsapp").error("whatsapp_scheduler_failed")
        await asyncio.sleep(10)
