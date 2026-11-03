"""Provider boundary. No tool execution or publishing authority is given to the model."""
import json
import re
from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel

from app.core.config import settings


class AIProviderError(Exception):
    """Public diagnostics are fixed strings, never raw provider bodies or credentials."""
    def __init__(self, provider_status: int):
        messages = {
            400: "Request AI ditolak provider. Periksa kompatibilitas adapter dan konfigurasi model.",
            401: "API key AI ditolak. Periksa key pada konfigurasi server.",
            403: "Akses AI ditolak. Periksa izin API key, model, dan project provider.",
            404: "Model atau endpoint AI tidak ditemukan. Periksa konfigurasi server.",
            429: "Kuota atau batas request AI tercapai. Periksa kuota provider atau coba lagi nanti.",
            503: "Model AI sedang sibuk di provider. Coba lagi beberapa saat.",
            504: "Provider AI terlalu lama merespons. Coba lagi nanti.",
        }
        self.detail = messages.get(provider_status, "Koneksi ke provider AI gagal. Periksa koneksi server dan coba lagi.")
        self.status_code = provider_status if provider_status in {429, 503, 504} else 502
        super().__init__(self.detail)


class AIService:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10), trust_env=False)
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()

    async def chat_api(self, system: str, user: str, max_tokens: int = 2048) -> str:
        payload = {"model": settings.AI_CHAT_MODEL,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "max_completion_tokens": max_tokens}
        if urlsplit(settings.AI_API_BASE_URL).hostname == "generativelanguage.googleapis.com":
            # Gemini rejects store; reasoning tokens also share the completion budget.
            payload["max_completion_tokens"] = max(max_tokens, 4096)
            payload["reasoning_effort"] = "low"
        else:
            payload["store"] = False
        response = await self.api_post("/chat/completions", payload)
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Respons model terpotong; gunakan batas output/model yang sesuai")
        content = choice["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model tidak menghasilkan teks")
        return content

    async def api_post(self, path: str, payload: dict):
        try:
            response = await self.client.post(
                settings.AI_API_BASE_URL.rstrip("/") + path,
                headers={"Authorization": f"Bearer {settings.AI_API_KEY}"}, json=payload)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(exc.response.status_code) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderError(504) from exc
        except httpx.RequestError as exc:
            raise AIProviderError(502) from exc

    async def text(self, system: str, user: str, max_tokens: int = 2048) -> str:
        if settings.AI_PROVIDER == "api":
            return await self.chat_api(system, user, max_tokens)
        from app.services.ollama_service import ollama_service
        return await ollama_service.chat(system, user, max_tokens=max_tokens)

    async def structured(self, system: str, data: dict, schema: type[BaseModel]) -> BaseModel:
        instruction = system + "\nKembalikan hanya satu objek JSON sesuai schema ini:\n" + json.dumps(schema.model_json_schema())
        response = await self.text(instruction, json.dumps(data, ensure_ascii=False), max_tokens=4096)
        response = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
        try:
            return schema.model_validate_json(response)
        except ValueError as exc:
            raise ValueError("Format hasil AI tidak valid. Coba generate kembali.") from exc

    async def embed_api(self, texts: list[str]) -> list[list[float]]:
        response = await self.api_post("/embeddings", {
            "model": settings.AI_EMBEDDING_MODEL, "input": texts, "encoding_format": "float"})
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        if [item["index"] for item in rows] != list(range(len(texts))):
            raise RuntimeError("Invalid embedding indexes")
        return [item["embedding"] for item in rows]


ai_service = AIService()
