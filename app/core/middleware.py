import asyncio
import hmac
import json
import logging
import re
import time
from collections import defaultdict, deque
from uuid import uuid4

from starlette.responses import JSONResponse
from app.core.config import settings
from app.core.security import tenant_context
from starlette.requests import Request
from app.services import auth_service as auth

log = logging.getLogger("http")
metrics = {"requests": 0, "errors": 0, "duration_ms": 0}


class SecurityMiddleware:
    """Single-worker staging admission control, identity, body limits and audit."""
    def __init__(self, app):
        self.app = app
        self.windows = defaultdict(deque)
        self.inflight = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"].rstrip("/")
        if not path.startswith("/api") or path == "/api/health":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        started = time.monotonic()
        headers = dict(scope["headers"])
        token = headers.get(b"authorization", b"").decode(errors="replace").removeprefix("Bearer ")
        principal = None
        for key, candidate in settings.API_KEYS.items():
            if hmac.compare_digest(token.encode(), key.encode()):
                principal = candidate
        session_auth = False
        if principal is None and not token and settings.AUTH_ENABLED:
            principal = await asyncio.to_thread(auth.resolve_session, Request(scope).cookies.get(auth.COOKIE_NAME))
            session_auth = principal is not None
        if principal is None and not settings.AUTH_ENABLED and settings.APP_ENV == "local" and not settings.API_KEYS:
            principal = {"username": "local", "tenant": "local", "role": "admin"}

        async def reject(status, detail, retry_after=None):
            response_headers = {"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
            if retry_after is not None:
                response_headers["Retry-After"] = str(retry_after)
            await JSONResponse({"detail": detail}, status_code=status, headers=response_headers)(scope, receive, send)
            elapsed = int((time.monotonic() - started) * 1000)
            metrics["requests"] += 1
            metrics["errors"] += int(status >= 500)
            metrics["duration_ms"] += elapsed
            log.info(json.dumps({"request_id": request_id, "method": scope["method"],
                                 "status": status, "duration_ms": elapsed,
                                 "tenant": principal["tenant"] if principal else "unauthenticated"}))

        public_auth = path in {"/api/auth/login", "/api/auth/logout"}
        if (session_auth or public_auth) and scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get(b"origin", b"").decode(errors="replace")
            expected = scope["scheme"] + "://" + headers.get(b"host", b"").decode(errors="replace")
            if headers.get(b"x-requested-with") != b"workspace" or (origin and origin != expected) or headers.get(b"sec-fetch-site") == b"cross-site":
                return await reject(403, "Request harus berasal dari aplikasi workspace.")
        if principal is None and not public_auth:
            return await reject(401, "Silakan login untuk mengakses workspace.")
        principal = principal or {"tenant": "unauthenticated", "role": "anonymous"}
        scope.setdefault("state", {})["principal"] = principal
        reader_paths = {"/api/chat-rag", "/api/knowledge/search", "/api/ready", "/api/llm/models",
                        "/api/assistant/messages", "/api/assistant/conversations"}
        own_conversation = re.fullmatch(r"/api/assistant/conversations/[a-f0-9]{32}", path)
        if principal["role"] != "admin" and not own_conversation and path not in reader_paths | {"/api/auth/me", "/api/auth/login", "/api/auth/logout"}:
            return await reject(403, "Akses admin diperlukan")
        now = time.monotonic()
        rate_key = token or (principal["tenant"] + ":" + principal.get("username", "session"))
        if path == "/api/auth/login":
            rate_key = "login:" + (scope.get("client") or ("unknown", 0))[0]
        window = self.windows[rate_key]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= (10 if path == "/api/auth/login" else settings.RATE_LIMIT_PER_MINUTE):
            return await reject(429, "Batas request tercapai; coba lagi nanti", retry_after=max(1, int(60 - (now - window[0]))))
        window.append(now)
        if self.inflight >= 4:
            return await reject(503, "Server sibuk; coba lagi nanti", retry_after=15)
        self.inflight += 1
        identity = tenant_context.set(principal["tenant"])
        status = 500
        response_started = False

        async def traced_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message.setdefault("headers", []).extend([
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"cache-control", b"no-store"),
                ])
            await send(message)

        async def run():
            # Bound memory before multipart/JSON parsing, including chunked requests.
            if path == "/api/documents/upload":
                limit = settings.MAX_UPLOAD_BYTES + 1024 * 1024
            elif re.fullmatch(r"/api/workspace/social/posts/[a-f0-9]{32}/image-upload", path):
                limit = min(10 * settings.MAX_UPLOAD_BYTES, 30 * 1024 * 1024) + 1024 * 1024
            else:
                limit = 256 * 1024
            chunks, length = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                block = message.get("body", b"")
                length += len(block)
                if length > limit:
                    return await JSONResponse({"detail": "Request terlalu besar"}, status_code=413)(scope, receive, traced_send)
                chunks.append(block)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            sent = False

            async def buffered_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()
            await self.app(scope, buffered_receive, traced_send)

        try:
            await asyncio.wait_for(run(), timeout=settings.REQUEST_TIMEOUT)
        except Exception as exc:
            # Never log bodies, credentials, prompts or exception strings.
            log.error("request_failed request_id=%s error_type=%s", request_id, type(exc).__name__)
            if not response_started:
                code = 504 if isinstance(exc, asyncio.TimeoutError) else 500
                await JSONResponse({"detail": "Layanan belum dapat memproses request", "request_id": request_id}, status_code=code)(scope, receive, traced_send)
        finally:
            self.inflight -= 1
            tenant_context.reset(identity)
            elapsed = int((time.monotonic() - started) * 1000)
            metrics["requests"] += 1
            metrics["errors"] += int(status >= 500)
            metrics["duration_ms"] += elapsed
            log.info(json.dumps({"request_id": request_id, "method": scope["method"],
                                "status": status, "duration_ms": elapsed, "tenant": principal["tenant"]}))
