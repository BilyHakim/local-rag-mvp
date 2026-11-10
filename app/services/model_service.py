from contextvars import ContextVar

import httpx

from app.core.config import settings
from app.services.ai_service import AIProviderError, ai_service
from app.services.ollama_service import ollama_service
from app.services.commandcode_plans import active_plan, model_allowed


chat_model_context: ContextVar[str | None] = ContextVar("chat_model", default=None)


async def list_chat_models() -> dict:
    provider = settings.AI_PROVIDER
    default = settings.AI_CHAT_MODEL if provider == "api" else settings.OLLAMA_CHAT_MODEL
    try:
        if provider == "api":
            response = await ai_service.client.get(
                settings.AI_API_BASE_URL.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            )
        else:
            response = await ollama_service.client.get(ollama_service.base_url + "/api/tags")
        response.raise_for_status()
        body = response.json()
        items = body.get("data", []) if provider == "api" else body.get("models", [])
        models = set()
        for item in items:
            endpoints = item.get("supported_endpoints")
            if endpoints is not None and not any(
                isinstance(endpoint, str) and endpoint.rstrip("/").endswith("/chat/completions")
                for endpoint in endpoints
            ):
                continue
            model = item.get("id") if provider == "api" else item.get("name")
            if isinstance(model, str) and model.strip() and model_allowed(model):
                models.add(model)
        available = sorted(models)
        if active_plan() == "goat" and default not in models:
            default = available[0] if available else ""
        return {"provider": provider, "default_model": default, "models": available, "plan": active_plan()}
    except httpx.HTTPStatusError as exc:
        raise AIProviderError(exc.response.status_code) from exc
    except httpx.TimeoutException as exc:
        raise AIProviderError(504) from exc
    except (httpx.RequestError, ValueError, TypeError, AttributeError) as exc:
        raise AIProviderError(502) from exc
