"""Explicitly approved publishing only. Ambiguous platform writes are never retried."""
import asyncio
import base64
import hashlib
import hmac
import html
import io
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from PIL import Image

from app.core.config import settings
from app.core.security import tenant_context
from app.services import workspace_store as store
from app.services.ai_service import ai_service


class PublishUncertain(Exception):
    pass


def connections():
    return settings.PUBLISHING_CONNECTIONS.get(tenant_context.get(), {})


def instagram_base():
    mode = connections().get("instagram_login_mode", "instagram")
    hosts = {"instagram": "graph.instagram.com", "unified": "graph.facebook.com"}
    if mode not in hosts:
        raise ValueError("instagram_login_mode harus instagram atau unified")
    return f"https://{hosts[mode]}/{settings.INSTAGRAM_API_VERSION}"


async def instagram_connection():
    config = connections()
    account = config.get("instagram_user_id", "")
    if not account.isdigit() or not config.get("instagram_access_token"):
        raise ValueError("Koneksi Instagram tenant ini belum dikonfigurasi")
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        result = await client.get(f"{instagram_base()}/{account}",
                                  headers={"Authorization": f"Bearer {config['instagram_access_token']}"},
                                  params={"fields": "id,username"})
        result.raise_for_status()
        data = result.json()
    return {"id": data["id"], "username": data["username"], "connected": True}


async def upload_image(post_id, revision, raw):
    post = await asyncio.to_thread(store.get, "post", post_id)
    allowed = {"draft", "approved", "scheduled", "failed"}
    if post["revision"] != revision or post["status"] not in allowed:
        raise ValueError("Muat ulang draft sebelum mengunggah gambar")
    if not raw or len(raw) > min(settings.MAX_UPLOAD_BYTES, 10 * 1024 * 1024):
        raise ValueError("Gambar maksimal 10 MB dan tidak boleh kosong")
    image_id = uuid4().hex
    path = image_path(image_id)

    def save():
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Gunakan gambar PNG, JPEG, atau WebP")
                if image.width * image.height > 20_000_000:
                    raise ValueError("Gambar maksimal 20 megapiksel")
                ratio = image.width / image.height
                if post["channel"] == "instagram" and not 0.8 <= ratio <= 1.91:
                    raise ValueError("Rasio gambar Instagram harus antara 4:5 dan 1.91:1")
                image.load()
                path.parent.mkdir(parents=True, exist_ok=True)
                image.convert("RGB").save(path, "JPEG", quality=90)
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("File gambar tidak valid atau rusak") from exc

    try:
        await asyncio.to_thread(save)
        return await asyncio.to_thread(store.update, "post", post_id, revision,
                                       dict(post, image_id=image_id, error=None), allowed=allowed)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def image_path(image_id, tenant=None):
    tenant = tenant or tenant_context.get()
    if not re.fullmatch(r"[a-z0-9_-]{1,48}", tenant) or not re.fullmatch(r"[a-f0-9]{32}", image_id or ""):
        raise ValueError("Identitas media tidak valid")
    return Path(settings.STORAGE_DIR) / "workspace_media" / tenant / f"{image_id}.jpg"


def public_image_url(image_id):
    parsed = urlsplit(settings.PUBLIC_BASE_URL)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("PUBLIC_BASE_URL harus URL HTTPS publik agar Meta dapat mengambil gambar")
    if len(settings.MEDIA_SIGNING_KEY) < 32:
        raise ValueError("MEDIA_SIGNING_KEY minimal 32 karakter diperlukan")
    tenant = tenant_context.get()
    expires = int(time.time()) + 86400
    signature = hmac.new(settings.MEDIA_SIGNING_KEY.encode(), f"{tenant}/{image_id}/{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/media/{tenant}/{image_id}?expires={expires}&signature={signature}"


def validate_signature(tenant, image_id, expires, signature):
    if len(settings.MEDIA_SIGNING_KEY) < 32 or expires < time.time() or expires > time.time() + 86460:
        return False
    expected = hmac.new(settings.MEDIA_SIGNING_KEY.encode(), f"{tenant}/{image_id}/{expires}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def generate_image(post_id, revision):
    post = await asyncio.to_thread(store.get, "post", post_id)
    if post["revision"] != revision or post["status"] not in {"draft", "approved", "scheduled", "failed"}:
        raise ValueError("Muat ulang draft sebelum membuat gambar")
    if not settings.IMAGE_API_KEY or not settings.IMAGE_MODEL:
        raise ValueError("Konfigurasikan IMAGE_API_KEY dan IMAGE_MODEL pada server")
    if not post.get("image_prompt"):
        raise ValueError("Brief gambar belum tersedia")
    response = await ai_service.client.post(
        settings.IMAGE_API_BASE_URL.rstrip("/") + "/images/generations",
        headers={"Authorization": f"Bearer {settings.IMAGE_API_KEY}"},
        json={"model": settings.IMAGE_MODEL, "prompt": post["image_prompt"], "n": 1, "size": "1024x1024"},
    )
    response.raise_for_status()
    encoded = response.json()["data"][0].get("b64_json")
    if not encoded or len(encoded) > 30_000_000:
        raise ValueError("Provider gambar harus mengembalikan b64_json (maksimal 22 MB)")
    raw = base64.b64decode(encoded, validate=True)
    image_id = uuid4().hex
    path = image_path(image_id)

    def save():
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Dimensi gambar terlalu besar")
            image.load()
            path.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(path, "JPEG", quality=90)
    await asyncio.to_thread(save)
    try:
        return await asyncio.to_thread(store.update, "post", post_id, revision, dict(post, image_id=image_id, error=None),
                                       allowed={"draft", "approved", "scheduled", "failed"})
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def full_caption(post):
    tags = " ".join("#" + tag.strip().lstrip("#").replace(" ", "") for tag in post.get("hashtags", []) if tag.strip())
    return post["caption"].strip() + ("\n\n" + tags if tags else "")


def validate_publishable(post):
    config = connections()
    if not post.get("title", "").strip() or not post.get("caption", "").strip():
        raise ValueError("Judul dan konten wajib diisi")
    if post["channel"] == "instagram":
        instagram_base()
        if not config.get("instagram_user_id", "").isdigit() or not config.get("instagram_access_token"):
            raise ValueError("Koneksi Instagram tenant ini belum dikonfigurasi")
        if len(full_caption(post)) > 2200:
            raise ValueError("Caption beserta hashtag Instagram maksimal 2200 karakter")
        if not post.get("image_id") or not image_path(post["image_id"]).is_file():
            raise ValueError("Instagram memerlukan gambar yang sudah dibuat")
        public_image_url(post["image_id"])
        if not re.fullmatch(r"v\d+\.\d+", settings.INSTAGRAM_API_VERSION):
            raise ValueError("Versi API Instagram tidak valid")
    else:
        url = urlsplit(config.get("wordpress_url", ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Konfigurasikan wordpress_url HTTPS yang valid")
        if not config.get("wordpress_username") or not config.get("wordpress_app_password"):
            raise ValueError("Koneksi WordPress tenant ini belum dikonfigurasi")


async def publish_instagram(post):
    config = connections()
    base = instagram_base()
    account = config["instagram_user_id"]
    headers = {"Authorization": f"Bearer {config['instagram_access_token']}"}
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.post(f"{base}/{account}/media", headers=headers,
                                     data={"image_url": public_image_url(post["image_id"]), "caption": full_caption(post)})
        response.raise_for_status()
        container = response.json()["id"]
        post = await asyncio.to_thread(store.update, "post", post["id"], post["revision"],
                                       dict(post, instagram_container_id=container), status="publishing", allowed={"publishing"})
        for attempt in range(12):
            status = await client.get(f"{base}/{container}", headers=headers, params={"fields": "status_code"})
            status.raise_for_status()
            code = status.json().get("status_code")
            if code == "FINISHED":
                break
            if code in {"ERROR", "EXPIRED"}:
                raise ValueError("Media ditolak Instagram; periksa format atau akses gambar")
            if attempt == 11:
                raise ValueError("Media belum siap. Belum ada posting yang diterbitkan.")
            await asyncio.sleep(2)
        # Any failure after this boundary may still have created a public post.
        try:
            response = await client.post(f"{base}/{account}/media_publish", headers=headers, data={"creation_id": container})
            response.raise_for_status()
            external_id = str(response.json()["id"])
        except Exception as exc:
            raise PublishUncertain() from exc
        link = None
        try:
            result = await client.get(f"{base}/{external_id}", headers=headers, params={"fields": "permalink"})
            result.raise_for_status()
            link = result.json().get("permalink")
        except Exception:
            pass
        return {"external_id": external_id, "external_url": link}


async def publish_wordpress(post):
    config = connections()
    base = config["wordpress_url"].rstrip("/") + "/wp-json/wp/v2"
    auth = httpx.BasicAuth(config["wordpress_username"], config["wordpress_app_password"])
    content = "\n".join(f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>" for part in post["caption"].split("\n\n") if part.strip())
    async with httpx.AsyncClient(timeout=30, trust_env=False, auth=auth) as client:
        media_id = None
        if post.get("image_id"):
            response = await client.post(base + "/media", content=await asyncio.to_thread(image_path(post["image_id"]).read_bytes),
                                         headers={"Content-Type": "image/jpeg", "Content-Disposition": f'attachment; filename="{post["id"]}.jpg"'})
            response.raise_for_status()
            media_id = response.json()["id"]
        # First create a private draft. Ambiguous draft creation cannot create a public duplicate.
        response = await client.post(base + "/posts", json={"title": post["title"], "content": content,
                                                           "status": "draft", **({"featured_media": media_id} if media_id else {})})
        response.raise_for_status()
        wp_id = response.json()["id"]
        post = await asyncio.to_thread(store.update, "post", post["id"], post["revision"],
                                       dict(post, wordpress_post_id=wp_id), status="publishing", allowed={"publishing"})
        try:
            response = await client.post(f"{base}/posts/{wp_id}", json={"status": "publish"})
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "publish":
                raise ValueError("WordPress belum mengonfirmasi status publish")
            return {"external_id": str(wp_id), "external_url": data.get("link")}
        except Exception as exc:
            raise PublishUncertain() from exc


async def publish_post(post_id, revision, *, scheduled=False):
    post = await asyncio.to_thread(store.get, "post", post_id)
    if post["revision"] != revision:
        raise ValueError("Versi konten berubah. Muat ulang posting.")
    if scheduled and (post["status"] != "scheduled" or not post["scheduled_at"] or post["scheduled_at"] > store.now_iso()):
        raise ValueError("Jadwal ini belum jatuh tempo atau telah dibatalkan")
    validate_publishable(post)
    post = await asyncio.to_thread(store.update, "post", post_id, revision, dict(post, error=None),
                                   status="publishing", allowed={"scheduled"} if scheduled else {"approved"})
    try:
        result = await (publish_instagram(post) if post["channel"] == "instagram" else publish_wordpress(post))
    except asyncio.CancelledError:
        current = store.get("post", post_id)
        store.update("post", post_id, current["revision"], dict(current, error="Proses terputus; periksa kanal sebelum mencoba ulang."), status="uncertain", allowed={"publishing"})
        raise
    except Exception as exc:
        current = await asyncio.to_thread(store.get, "post", post_id)
        uncertain = isinstance(exc, PublishUncertain)
        return await asyncio.to_thread(store.update, "post", post_id, current["revision"],
                                       dict(current, error="Hasil publish belum pasti; periksa kanal dan rekonsiliasi sebelum mencoba ulang." if uncertain else "Gagal menyiapkan publikasi; periksa konfigurasi, token, dan media. Belum diterbitkan."),
                                       status="uncertain" if uncertain else "failed", allowed={"publishing"})
    current = await asyncio.to_thread(store.get, "post", post_id)
    return await asyncio.to_thread(store.update, "post", post_id, current["revision"], dict(current, **result, error=None),
                                   status="published", allowed={"publishing"})


async def scheduler_tick():
    await asyncio.to_thread(store.recover_stale_jobs)
    for tenant, post_id in await asyncio.to_thread(store.due_jobs):
        identity = tenant_context.set(tenant)
        post = None
        try:
            post = await asyncio.to_thread(store.get, "post", post_id)
            if post["status"] != "scheduled" or not post["scheduled_at"] or post["scheduled_at"] > store.now_iso():
                continue
            await publish_post(post_id, post["revision"], scheduled=True)
        except (ValueError, KeyError):
            # Invalid configuration must not cause repeated posting attempts every tick.
            try:
                current = await asyncio.to_thread(store.get, "post", post_id)
            except KeyError:
                continue
            if post and current["status"] == "scheduled" and current["revision"] == post["revision"]:
                await asyncio.to_thread(store.update, "post", post_id, current["revision"],
                                        dict(current, error="Jadwal gagal divalidasi; periksa koneksi lalu setujui/jadwalkan ulang."),
                                        status="failed", allowed={"scheduled"})
        finally:
            tenant_context.reset(identity)


async def scheduler_loop():
    import logging
    while True:
        try:
            await scheduler_tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger("planner").error("scheduler_tick_failed")
        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
