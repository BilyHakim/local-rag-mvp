"""Provider boundary. No tool execution or publishing authority is given to the model."""
import json
import re
import httpx
from pydantic import BaseModel

from app.core.config import settings


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
        response = await self.client.post(
            settings.AI_API_BASE_URL.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            json={"model": settings.AI_CHAT_MODEL, "store": False,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                  "max_completion_tokens": max_tokens},
        )
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Respons model terpotong; gunakan batas output/model yang sesuai")
        content = choice["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model tidak menghasilkan teks")
        return content

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
        response = await self.client.post(
            settings.AI_API_BASE_URL.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            json={"model": settings.AI_EMBEDDING_MODEL, "input": texts, "encoding_format": "float"},
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        if [item["index"] for item in rows] != list(range(len(texts))):
            raise RuntimeError("Invalid embedding indexes")
        return [item["embedding"] for item in rows]


ai_service = AIService()
