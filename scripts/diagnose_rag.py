"""Check local RAG dependencies without printing credentials or sending LLM prompts."""
import asyncio
import argparse
import json
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-chat", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--trace-rag", action="store_true")
    args = parser.parse_args()
    print(json.dumps({
        "text_provider": settings.AI_PROVIDER,
        "text_host": urlsplit(settings.AI_API_BASE_URL).hostname,
        "default_model": settings.AI_CHAT_MODEL,
        "api_key_configured": bool(settings.AI_API_KEY),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.OLLAMA_EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER == "ollama" else settings.AI_EMBEDDING_MODEL,
    }))
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        for name, url in [
            ("ollama", settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"),
            ("qdrant", settings.QDRANT_URL.rstrip("/") + "/collections"),
            ("app", "http://127.0.0.1:8000/api/health"),
        ]:
            try:
                headers = {"api-key": settings.QDRANT_API_KEY} if name == "qdrant" and settings.QDRANT_API_KEY else {}
                response = await client.get(url, headers=headers)
                result = {"service": name, "http_status": response.status_code}
                if name == "ollama" and response.status_code == 200:
                    result["models"] = [model["name"] for model in response.json().get("models", [])]
                if name == "qdrant" and response.status_code == 200:
                    result["collection_count"] = len(response.json().get("result", {}).get("collections", []))
                print(json.dumps(result))
            except httpx.RequestError as exc:
                print(json.dumps({"service": name, "error_type": type(exc).__name__}))
        if args.verify_chat:
            for question in ["Haloo", "Apa saja layanan perusahaan?"]:
                try:
                    response = await client.post("http://127.0.0.1:8000/api/chat-rag",
                                                 json={"question": question, "model": args.model}, timeout=180)
                    body = response.json()
                    print(json.dumps({"check": "greeting" if question == "Haloo" else "rag",
                                      "http_status": response.status_code,
                                      "status": body.get("status"), "code": body.get("code"),
                                      "detail": body.get("detail") if body.get("code") == "ai_provider_error" else None,
                                      "answer_present": bool(body.get("answer")),
                                      "sources": len(body.get("sources", []))}), flush=True)
                except httpx.RequestError as exc:
                    print(json.dumps({"check": "chat", "error_type": type(exc).__name__}), flush=True)
    if args.trace_rag:
        from app.services.rag_service import answer_with_rag
        from app.services.model_service import chat_model_context
        from app.services.ai_service import ai_service, AIProviderError
        from app.services.ollama_service import ollama_service
        token = chat_model_context.set(args.model)
        try:
            result = await answer_with_rag("Apa saja layanan perusahaan?")
            print(json.dumps({"direct_rag": result["status"]}))
        except Exception as exc:
            print(json.dumps({"error_type": type(exc).__name__,
                              "detail": exc.detail if isinstance(exc, AIProviderError) else None,
                              "frames": [
                {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(exc.__traceback__)
            ]}))
        finally:
            chat_model_context.reset(token)
            await ai_service.close()
            await ollama_service.close()


if __name__ == "__main__":
    asyncio.run(main())
