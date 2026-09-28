import math
import httpx

from app.core.config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL
        self._client = None

    @property
    def client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5),
                                           limits=httpx.Limits(max_connections=16))
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()

    async def _post(self, endpoint, payload):
        response = await self.client.post(f"{self.base_url}/api/{endpoint}", json=payload)
        response.raise_for_status()
        return response.json()

    async def generate(self, prompt: str) -> str:
        data = await self._post("generate", {"model": self.chat_model, "prompt": prompt,
                               "stream": False, "options": {"temperature": 0, "num_predict": 512}})
        return data["response"]

    async def chat(self, system_prompt: str, user_prompt: str, *, max_tokens: int | None = None) -> str:
        data = await self._post("chat", {
            "model": self.chat_model, "stream": False,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "options": {"temperature": 0, "num_predict": max_tokens or 512},
        })
        return data["message"]["content"]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        data = await self._post("embed", {"model": self.embedding_model, "input": texts, "truncate": False})
        vectors = data.get("embeddings", [])
        if (len(vectors) != len(texts) or not vectors or not vectors[0]
                or any(len(v) != len(vectors[0]) or not all(math.isfinite(x) for x in v) for v in vectors)):
            raise RuntimeError("Invalid embedding response")
        return vectors

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_many([text]))[0]


ollama_service = OllamaService()
