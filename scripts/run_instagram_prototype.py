import argparse
import asyncio
import json
import re
import secrets
import socket
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main():
    parser = argparse.ArgumentParser(description="Local Instagram prototype with a public signed-media gateway")
    parser.add_argument("--cloudflared", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--media-port", type=int, default=8012)
    args = parser.parse_args()

    if not 1 <= args.port <= 65535 or not 1 <= args.media_port <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    if args.port == args.media_port:
        raise SystemExit("UI and media ports must be different.")
    if not args.cloudflared.is_file():
        raise SystemExit(
            f"cloudflared tidak ditemukan: {args.cloudflared.resolve()}. "
            "Unduh cloudflared.exe dari https://developers.cloudflare.com/tunnel/downloads/ "
            "lalu gunakan --cloudflared dengan lokasi file tersebut. "
            "Belum ada request Instagram atau AI yang dikirim."
        )
    sockets = []
    try:
        for port in (args.port, args.media_port):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(listener)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind(("127.0.0.1", port))
                listener.listen(2048)
                listener.setblocking(False)
            except OSError:
                raise SystemExit(
                    f"Port {port} tidak tersedia. Hentikan prototype lama dengan Ctrl+C, "
                    "atau pilih dua port kosong dengan --port 8021 --media-port 8022. "
                    "Belum ada request Instagram atau AI yang dikirim."
                ) from None
        await run(args, sockets[0], sockets[1])
    finally:
        for listener in sockets:
            listener.close()


async def run(args, app_socket, media_socket):

    import uvicorn
    from fastapi import FastAPI
    from app.core.config import settings
    from app.core.security import tenant_context
    from app.services import workspace_store as store
    from app.services.publishing_service import upload_image, instagram_connection

    if settings.APP_ENV != "local" or settings.API_KEYS:
        raise SystemExit("This launcher requires local mode without API_KEYS. Use the normal authenticated deployment otherwise.")
    config = settings.PUBLISHING_CONNECTIONS.get("local", {})
    if not config.get("instagram_user_id") or not config.get("instagram_access_token"):
        raise SystemExit("Instagram credentials for local are not configured. No publishing attempted.")
    config["instagram_login_mode"] = "unified"
    settings.SCHEDULER_ENABLED = False
    settings.MEDIA_SIGNING_KEY = settings.MEDIA_SIGNING_KEY if len(settings.MEDIA_SIGNING_KEY) >= 32 else secrets.token_urlsafe(32)
    tenant_context.set("local")
    try:
        identity = await instagram_connection()
    except Exception as exc:
        raise SystemExit(f"Instagram connection failed ({type(exc).__name__}). No publishing attempted.") from None
    print("Instagram identity: " + json.dumps(identity), flush=True)

    from app.main import app
    from app.api.workspace import media_router
    media = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    media.include_router(media_router)
    media_server = uvicorn.Server(uvicorn.Config(media, host="127.0.0.1", port=args.media_port, access_log=False, log_level="warning"))
    media_task = asyncio.create_task(media_server.serve(sockets=[media_socket]))
    tunnel = None
    app_server = None
    try:
        for _ in range(100):
            if media_task.done():
                await media_task
                raise RuntimeError("Media gateway could not start")
            if media_server.started:
                break
            await asyncio.sleep(0.1)
        if not media_server.started:
            raise RuntimeError("Media gateway startup timeout")
        tunnel = await asyncio.create_subprocess_exec(str(args.cloudflared.resolve()), "tunnel", "--url",
                   f"http://127.0.0.1:{args.media_port}", "--protocol", "http2", "--no-autoupdate",
                   stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        async def public_url():
            while line := await tunnel.stderr.readline():
                match = re.search(rb"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if match:
                    return match.group().decode()
            raise RuntimeError("Tunnel did not return a public URL")
        settings.PUBLIC_BASE_URL = await asyncio.wait_for(public_url(), timeout=45)
        print("Public signed-media gateway: " + settings.PUBLIC_BASE_URL, flush=True)
        async def drain_tunnel():
            while await tunnel.stderr.readline():
                pass
        drain_task = asyncio.create_task(drain_tunnel())
        record_id = "c" * 32
        try:
            post = store.get("post", record_id)
        except KeyError:
            post = store.create("post", {"channel": "instagram", "title": "Tes integrasi Instagram",
                "caption": "Tes publikasi dari Local RAG ke Instagram. Thumbnail dibuat dengan bantuan AI untuk pengujian prototype Cyberbily.",
                "image_prompt": "", "hashtags": [], "notes": "Draft uji, periksa sebelum publikasi.",
                "history": [], "sources": [], "warnings": []}, record_id=record_id)
        if not post.get("image_id") and post["status"] == "draft":
            post = await upload_image(post["id"], post["revision"], (ROOT / "assets/instagram/thumbnail-tes-integrasi.png").read_bytes())
        print("Prototype post: " + post["id"] + "; status: " + post["status"], flush=True)
        print(f"Local UI: http://127.0.0.1:{args.port}/#social", flush=True)
        app_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning"))
        await app_server.serve(sockets=[app_socket])
    finally:
        media_server.should_exit = True
        if tunnel is not None and tunnel.returncode is None:
            tunnel.terminate()
            await tunnel.wait()
        await media_task


if __name__ == "__main__":
    asyncio.run(main())
