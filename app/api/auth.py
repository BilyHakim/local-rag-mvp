import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal

from app.core.config import settings
from app.services import auth_service as auth


router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class AccountEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0)
    display_name: str = Field(min_length=1, max_length=100)
    email: str = Field(default="", max_length=254)
    bio: str = Field(default="", max_length=1000)
    default_model: str = Field(default="", max_length=200)
    enabled_features: list[Literal["assistant", "chat", "seo", "social"]] = Field(max_length=4)

    @field_validator("email")
    @classmethod
    def contact_email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Format email kontak tidak valid")
        return value

    @field_validator("enabled_features")
    @classmethod
    def unique_features(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Pilihan fitur tidak boleh berulang")
        return value


class PasswordEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


async def account_session(request):
    principal = await asyncio.to_thread(auth.resolve_session, request.cookies.get(auth.COOKIE_NAME))
    return principal if not request.headers.get("authorization") and principal == request.state.principal else None


@router.get("/api/account/profile")
async def account_profile(request: Request):
    session = await account_session(request)
    return await asyncio.to_thread(auth.account_profile, request.state.principal, editable=bool(session))


@router.put("/api/account/profile")
async def edit_account(payload: AccountEdit, request: Request):
    session = await account_session(request)
    if not session:
        raise HTTPException(403, "Login dengan akun workspace untuk mengedit profil.")
    try:
        return await asyncio.to_thread(auth.save_account_profile, session, payload.revision, payload.model_dump(exclude={"revision"}))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/api/account/password")
async def edit_password(payload: PasswordEdit, request: Request):
    session = await account_session(request)
    if not session:
        raise HTTPException(403, "Login dengan akun workspace untuk mengganti password.")
    try:
        await asyncio.to_thread(auth.change_password, session["username"], payload.current_password,
                                payload.new_password, request.cookies.get(auth.COOKIE_NAME))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"message": "Password diperbarui. Sesi login lainnya sudah dikeluarkan."}


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
