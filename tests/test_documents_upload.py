import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import UploadFile

from app.api.documents import upload_document
from app.services.dedup_service import compute_content_hash


@pytest.mark.asyncio
async def test_upload_document_skips_duplicate_without_embedding():
    content = b"duplicate csv content"
    content_hash = compute_content_hash(content)
    upload = UploadFile(filename="sample.csv", file=io.BytesIO(content))

    with patch("app.api.documents.qdrant_service.exists_by_content_hash", return_value=True), patch(
        "app.api.documents.qdrant_service.get_sample_by_content_hash",
        return_value={"saved_path": "storage/documents/existing.csv"},
    ), patch("app.api.documents.ollama_service.embed", new_callable=AsyncMock) as embed_mock:
        response = await upload_document(upload)

    embed_mock.assert_not_called()
    assert response.skipped_duplicate is True
    assert response.content_hash == content_hash
    assert response.indexed_chunks == 0
    assert response.saved_path == "storage/documents/existing.csv"


@pytest.mark.asyncio
async def test_upload_document_uses_deterministic_point_id_for_csv_row():
    csv_content = b"tanggal,kategori\n2026-01-01,Transportasi\n"
    content_hash = compute_content_hash(csv_content)
    upload = UploadFile(filename="keuangan.csv", file=io.BytesIO(csv_content))
    captured_point_ids: list[str] = []

    def capture_upsert(**kwargs):
        captured_point_ids.append(kwargs["point_id"])
        return kwargs["point_id"]

    with patch("app.api.documents.qdrant_service.exists_by_content_hash", return_value=False), patch(
        "app.api.documents.qdrant_service.delete_by_filename"
    ), patch(
        "app.api.documents.ollama_service.embed",
        new_callable=AsyncMock,
        return_value=[0.1] * 8,
    ), patch("app.api.documents.qdrant_service.upsert_text", side_effect=capture_upsert):
        response = await upload_document(upload)

    assert response.skipped_duplicate is False
    assert response.indexed_chunks >= 1
    assert len(captured_point_ids) == response.indexed_chunks
    assert len(set(captured_point_ids)) == len(captured_point_ids)

    second_upload = UploadFile(filename="keuangan_copy.csv", file=io.BytesIO(csv_content))
    second_point_ids: list[str] = []

    def capture_second(**kwargs):
        second_point_ids.append(kwargs["point_id"])
        return kwargs["point_id"]

    with patch("app.api.documents.qdrant_service.exists_by_content_hash", return_value=False), patch(
        "app.api.documents.qdrant_service.delete_by_filename"
    ), patch(
        "app.api.documents.ollama_service.embed",
        new_callable=AsyncMock,
        return_value=[0.1] * 8,
    ), patch("app.api.documents.qdrant_service.upsert_text", side_effect=capture_second):
        await upload_document(second_upload)

    assert captured_point_ids == second_point_ids
