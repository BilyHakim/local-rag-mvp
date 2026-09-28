import httpx
import pytest

from app.services.ollama_service import OllamaService


async def test_batch_embedding_rejects_partial_response_and_reuses_client():
    service = OllamaService()
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"embeddings": [[1., 0.]]})))
    original = service.client
    try:
        with pytest.raises(RuntimeError):
            await service.embed_many(["first", "second"])
        assert await service.embed("first") == [1., 0.]
        assert service.client is original
    finally:
        await service.close()
    assert original.is_closed


async def test_batch_embedding_disables_silent_truncation():
    import json
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": [[1., 0.], [0., 1.]]})

    service = OllamaService()
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        assert len(await service.embed_many(["first", "second"])) == 2
        assert requests[0]["input"] == ["first", "second"]
        assert requests[0]["truncate"] is False
    finally:
        await service.close()
