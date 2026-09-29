from unittest.mock import AsyncMock
import warnings

import httpx
import pytest
from qdrant_client import QdrantClient
from app.core.config import settings, Settings
from app.core.security import tenant_context
from app.services import index_manifest, ingestion_service
from app.services.qdrant_service import QdrantService
from app.services.rag_service import is_answer_grounded, reciprocal_rank_fusion
from app.services.chunking_service import chunk_text
from app.services.postgres_service import resolve_connection
from app.schemas.postgres import PostgresConnectionOverride
from app.main import app


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "EMBED_BATCH_SIZE", 1)
    token = tenant_context.set("alpha")
    service = QdrantService()
    service.client.close()
    service.client = QdrantClient(":memory:")
    monkeypatch.setattr(ingestion_service, "qdrant_service", service)
    monkeypatch.setattr(ingestion_service.ollama_service, "embed_many", AsyncMock(side_effect=lambda texts: [[1., 0.] for _ in texts]))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Payload indexes have no effect.*")
        yield service
    service.client.close()
    tenant_context.reset(token)


async def test_failed_replacement_is_invisible_to_dense_and_bm25(corpus, monkeypatch):
    await ingestion_service.ingest("doc", [{"text": "FM01 address 247"}])
    old = index_manifest.versions()
    monkeypatch.setattr(ingestion_service.ollama_service, "embed_many", AsyncMock(side_effect=[[[1., 0.]], RuntimeError("embedding failed")]))
    with pytest.raises(RuntimeError):
        await ingestion_service.ingest("doc", [{"text": "replacement address 888"}, {"text": "last"}])
    assert index_manifest.versions() == old
    assert [x["text"] for x in corpus.search([1., 0.])] == ["FM01 address 247"]
    assert index_manifest.lexical("replacement", 5) == []
    assert len(index_manifest.lexical("FM01", 5)) == 1


async def test_successful_replacement_and_snapshot_and_empty_sync(corpus):
    await ingestion_service.ingest("doc", [{"text": "old data"}])
    snapshot = index_manifest.versions()
    await ingestion_service.ingest("doc", [{"text": "new data"}])
    assert [x["text"] for x in corpus.search([1., 0.])] == ["new data"]
    assert [x["text"] for x in corpus.search([1., 0.], active_versions=snapshot)] == ["old data"]
    assert index_manifest.lexical("old", 5) == []
    await ingestion_service.ingest("doc", [], allow_empty=True)
    assert corpus.search([1., 0.]) == []
    assert index_manifest.lexical("data", 5) == []


async def test_tenants_cannot_read_each_others_sources(corpus):
    await ingestion_service.ingest("same", [{"text": "alpha private", "content_hash": "hash"}])
    token = tenant_context.set("beta")
    try:
        assert corpus.get_sample_by_content_hash("hash") is None
        assert corpus.search([1., 0.]) == []
        assert index_manifest.lexical("private", 5) == []
        await ingestion_service.ingest("same", [{"text": "beta private"}])
        assert [x["text"] for x in corpus.search([1., 0.])] == ["beta private"]
    finally:
        tenant_context.reset(token)
    assert [x["text"] for x in corpus.search([1., 0.])] == ["alpha private"]


async def test_auth_role_and_body_limit(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "API_KEYS", {"a" * 32: {"tenant": "alpha", "role": "reader"}, "b" * 32: {"tenant": "beta", "role": "admin"}})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/chat-rag", json={"question": "test"})).status_code == 401
        assert (await client.post("/api/knowledge", headers={"Authorization": "Bearer " + "a" * 32}, json={"text": "test"})).status_code == 403
        response = await client.post("/api/chat-rag", headers={"Authorization": "Bearer " + "b" * 32}, content=b"x" * 300000)
        assert response.status_code == 413
        assert response.headers["x-request-id"]
        assert (await client.get("/api/health")).status_code == 200


def test_configuration_and_numeric_guard():
    with pytest.raises(ValueError):
        Settings(_env_file=None, APP_ENV="staging", API_KEYS={})
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=2, overlap=2)
    assert chunk_text("abcdef", chunk_size=3, overlap=0) == ["abc", "def"]
    assert not is_answer_grounded("12", [{"text": "312"}])
    assert not is_answer_grounded("7", [{"text": "9"}])
    assert not is_answer_grounded("", [{"text": "data"}])


def test_override_blocked_in_staging(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    with pytest.raises(ValueError):
        resolve_connection(PostgresConnectionOverride(host="169.254.169.254"))


def test_rrf_rewards_agreement_without_comparing_raw_scales():
    result = reciprocal_rank_fusion([{"id": "a", "score": .9}, {"id": "b", "score": .5}], [{"id": "b", "score": 1000}])
    assert result[0]["id"] == "b"


async def test_http_upload_retrieve_citations_and_tenant_boundary(corpus, monkeypatch):
    import app.api.documents as documents
    import app.services.rag_service as rag
    monkeypatch.setattr(documents, "qdrant_service", corpus)
    monkeypatch.setattr(rag, "qdrant_service", corpus)
    monkeypatch.setattr(rag.ollama_service, "chat", AsyncMock(side_effect=["E1", "247", "PASS"]))
    monkeypatch.setattr(settings, "API_KEYS", {
        "c" * 32: {"tenant": "alpha", "role": "admin"},
        "d" * 32: {"tenant": "alpha", "role": "reader"},
        "e" * 32: {"tenant": "beta", "role": "reader"},
    })
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/documents/upload", headers={"Authorization": "Bearer " + "c" * 32},
                                     files={"file": ("sensor.csv", b"sensor,address\nFM01,247", "text/csv")})
        assert response.status_code == 200, response.text
        response = await client.post("/api/chat-rag", headers={"Authorization": "Bearer " + "d" * 32}, json={"question": "Alamat FM01?"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["answer"] == "247"
        assert body["citations"][0]["row_number"] == 2
        assert body["citations"][0]["source_id"] == body["sources"][0]["id"]
        response = await client.post("/api/chat-rag", headers={"Authorization": "Bearer " + "e" * 32, "X-Tenant-ID": "alpha"}, json={"question": "Alamat FM01?"})
        assert response.status_code == 200
        assert response.json()["status"] == "insufficient_evidence"
        assert response.json()["sources"] == []


async def test_postgres_allowlist_validated_before_connection(monkeypatch):
    import app.services.postgres_service as postgres
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "POSTGRES_ALLOWED_TABLES", ["sensors"])
    connect = AsyncMock()
    monkeypatch.setattr(postgres, "_connect", connect)
    with pytest.raises(ValueError):
        await postgres.sync_tables(tables=["passwords"])
    with pytest.raises(ValueError):
        await postgres.sync_tables(tables=["sensors"], limit_per_table=1)
    connect.assert_not_called()


async def test_postgres_table_list_filters_disallowed_tables(monkeypatch):
    import app.services.postgres_service as postgres
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "POSTGRES_ALLOWED_TABLES", ["sensors"])
    connection = AsyncMock()
    connection.fetch.return_value = [{"table_name": "sensors", "row_estimate": 1}, {"table_name": "passwords", "row_estimate": 1}]
    monkeypatch.setattr(postgres, "_connect", AsyncMock(return_value=connection))
    result = await postgres.list_tables()
    assert [t["name"] for t in result["tables"]] == ["sensors"]


def test_eval_fixture_bm25_baseline(corpus):
    import json
    from pathlib import Path
    dataset = json.loads((Path(__file__).parents[1] / "evals/staging.json").read_text())
    for i, document in enumerate(dataset["documents"]):
        index_manifest.publish(document["source_name"], str(i), [dict(document, id=str(i))])
    for case in dataset["cases"]:
        if case.get("fallback"):
            continue
        sources = {x["source_name"] for x in index_manifest.lexical(case["question"], 5)}
        assert set(case["sources"]).issubset(sources), case["id"]


async def test_source_quota_preserves_existing_publication(corpus, monkeypatch):
    monkeypatch.setattr(settings, "MAX_SOURCES_PER_TENANT", 1)
    await ingestion_service.ingest("one", [{"text": "old"}])
    await ingestion_service.ingest("one", [{"text": "updated"}])
    with pytest.raises(ValueError):
        await ingestion_service.ingest("two", [{"text": "forbidden"}])
    assert [x["text"] for x in corpus.search([1., 0.])] == ["updated"]
    assert index_manifest.lexical("forbidden", 5) == []


async def test_embedding_change_requires_reindex(corpus, monkeypatch):
    await ingestion_service.ingest("one", [{"text": "old"}])
    monkeypatch.setattr(settings, "OLLAMA_EMBEDDING_MODEL", "different")
    with pytest.raises(ValueError):
        await ingestion_service.ingest("one", [{"text": "new"}])


async def test_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "API_KEYS", {"r" * 32: {"tenant": "alpha", "role": "admin"}})
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer " + "r" * 32}
        assert (await client.get("/api/metrics", headers=headers)).status_code == 200
        rejected = await client.get("/api/metrics", headers=headers)
        assert rejected.status_code == 429
        assert rejected.headers["retry-after"]
        assert rejected.headers["x-request-id"]


async def test_overload_response_is_traceable(monkeypatch):
    from app.core.middleware import SecurityMiddleware
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "API_KEYS", {"q" * 32: {"tenant": "alpha", "role": "reader"}})
    middleware = SecurityMiddleware(app)
    middleware.inflight = 4
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=middleware), base_url="http://test") as client:
        response = await client.get("/api/ready", headers={"Authorization": "Bearer " + "q" * 32})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "15"
    assert response.headers["x-request-id"]
