import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
import app.api.documents as documents
from app.core.config import settings


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(documents.qdrant_service, "get_sample_by_content_hash", lambda _: None)


async def test_duplicate_does_not_embed(monkeypatch, tmp_path):
    monkeypatch.setattr(documents.qdrant_service, "get_sample_by_content_hash", lambda _: {"filename": "sample.csv"})
    ingest = AsyncMock()
    monkeypatch.setattr(documents, "ingest", ingest)
    result = await documents.upload_document(UploadFile(filename="sample.csv", file=io.BytesIO(b"a,b\n1,2")))
    assert result.skipped_duplicate
    ingest.assert_not_called()
    assert not list(tmp_path.rglob("*.csv"))


async def test_csv_preserves_metadata_and_sanitizes_filename(monkeypatch):
    ingest = AsyncMock()
    monkeypatch.setattr(documents, "ingest", ingest)
    result = await documents.upload_document(UploadFile(filename="../../sample.csv", file=io.BytesIO(b"sensor,address\nFM01,247")))
    assert result.filename == "sample.csv"
    records = ingest.call_args.args[1]
    assert records[0]["row_number"] == 2
    assert "address: 247" in records[0]["text"]


async def test_failed_ingestion_cleans_file_without_deleting_old_index(monkeypatch, tmp_path):
    monkeypatch.setattr(documents, "ingest", AsyncMock(side_effect=RuntimeError("offline")))
    deletion = AsyncMock()
    monkeypatch.setattr(documents.qdrant_service, "delete_by_filename", deletion)
    with pytest.raises(RuntimeError):
        await documents.upload_document(UploadFile(filename="sample.csv", file=io.BytesIO(b"a,b\n1,2")))
    deletion.assert_not_called()
    assert not list(tmp_path.rglob("*.csv"))


async def test_upload_enforces_backend_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 3)
    with pytest.raises(HTTPException) as exc:
        await documents.upload_document(UploadFile(filename="sample.csv", file=io.BytesIO(b"1234")))
    assert exc.value.status_code == 413
    assert not list(tmp_path.rglob("*.csv"))
