import httpx

from app.core.config import settings

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model = settings.OLLAMA_CHAT_MODEL

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

ollama_service = OllamaService()