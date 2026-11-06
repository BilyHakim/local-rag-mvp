import asyncio
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import auth_service as auth


router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    if not settings.AUTH_ENABLED or await asyncio.to_thread(auth.resolve_session, request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
    return FileResponse(Path(__file__).resolve().parents[1] / "static/login.html", headers={"Cache-Control": "no-store"})


@router.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request):
    token = await asyncio.to_thread(auth.authenticate, payload.username, payload.password, request.cookies.get(auth.COOKIE_NAME))
    if not token:
        return JSONResponse({"detail": "Username atau password salah."}, status_code=401)
    response = JSONResponse({"username": payload.username})
    response.set_cookie(auth.COOKIE_NAME, token, max_age=auth.SESSION_SECONDS, httponly=True,
                        secure=settings.APP_ENV != "local" or request.url.scheme == "https", samesite="lax", path="/")
    return response


@router.get("/api/auth/me")
async def me(request: Request):
    return request.state.principal


@router.post("/api/auth/logout")
async def logout(request: Request):
    await asyncio.to_thread(auth.revoke_session, request.cookies.get(auth.COOKIE_NAME))
    response = JSONResponse({"message": "Sesi berakhir."})
    response.delete_cookie(auth.COOKIE_NAME, path="/", httponly=True, samesite="lax",
                           secure=settings.APP_ENV != "local" or request.url.scheme == "https")
    return response
