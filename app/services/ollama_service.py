import httpx

from app.core.config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL

    async def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.chat_model,
            "prompt": prompt,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()
        return data["response"]

    async def embed(self, text: str) -> list[float]:
        url = f"{self.base_url}/api/embed"

        payload = {
            "model": self.embedding_model,
            "input": text,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()

        embeddings = data.get("embeddings")
        if not embeddings or not embeddings[0]:
            raise RuntimeError(f"Embedding response tidak valid: {data}")

        return embeddings[0]


ollama_service = OllamaService()