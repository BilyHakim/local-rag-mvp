import uuid

import httpx
import pytest

from app.services.dedup_service import compute_content_hash, document_point_id
from app.services.qdrant_service import QdrantService


def _qdrant_available() -> bool:
    try:
        response = httpx.get("http://localhost:6333/collections", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_available(),
    reason="Qdrant tidak berjalan di localhost:6333",
)


@pytest.fixture()
def isolated_qdrant_service(monkeypatch):
    collection_name = f"test_dedup_{uuid.uuid4().hex}"
    monkeypatch.setattr(
        "app.services.qdrant_service.settings.QDRANT_COLLECTION",
        collection_name,
    )
    service = QdrantService()
    yield service
    if service._collection_exists():
        service.client.delete_collection(collection_name)


def test_exists_by_content_hash_and_delete_by_filename(isolated_qdrant_service):
    service = isolated_qdrant_service
    content_hash = compute_content_hash(b"integration-test-file")
    vector = [0.0] * 8

    point_id = document_point_id(content_hash, page_number=1, chunk_index=0)
    service.upsert_text(
        vector=vector,
        text="sensor_id: FM01; modbus_address: 247",
        source_name="sensor_values.csv",
        metadata={
            "filename": "sensor_values.csv",
            "content_hash": content_hash,
            "saved_path": "/tmp/sensor_values.csv",
        },
        point_id=point_id,
    )

    assert service.exists_by_content_hash(content_hash) is True

    sample = service.get_sample_by_content_hash(content_hash)
    assert sample is not None
    assert sample["text"].startswith("sensor_id: FM01")
    assert sample["saved_path"] == "/tmp/sensor_values.csv"

    service.delete_by_filename("sensor_values.csv")
    assert service.exists_by_content_hash(content_hash) is False


def test_upsert_same_point_id_overwrites_not_duplicates(isolated_qdrant_service):
    service = isolated_qdrant_service
    content_hash = compute_content_hash(b"overwrite-test")
    point_id = document_point_id(content_hash, page_number=1, chunk_index=0)

    service.upsert_text(
        vector=[0.1] * 8,
        text="version 1",
        source_name="doc.txt",
        metadata={"filename": "doc.txt", "content_hash": content_hash},
        point_id=point_id,
    )
    service.upsert_text(
        vector=[0.2] * 8,
        text="version 2",
        source_name="doc.txt",
        metadata={"filename": "doc.txt", "content_hash": content_hash},
        point_id=point_id,
    )

    records, _ = service.client.scroll(
        collection_name=service.collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    assert len(records) == 1
    assert records[0].payload["text"] == "version 2"
