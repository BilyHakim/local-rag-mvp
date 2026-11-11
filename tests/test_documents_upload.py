import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
import app.api.documents as documents
from app.core.config import settings


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(documents.qdrant_service, "get_sample_by_content_hash", lambda *args: None)


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


async def test_folder_keeps_same_named_files_separate_and_detects_uppercase_extension(monkeypatch):
    ingest = AsyncMock()
    monkeypatch.setattr(documents, 'ingest', ingest)
    for folder in ('Knowledge/finance', 'Knowledge/operations'):
        result = await documents.upload_document(UploadFile(filename='report.CSV', file=io.BytesIO(b'name,value\nsensor,247')), relative_path=folder + '/report.CSV')
        assert result.filename == folder + '/report.CSV'
        source, records = ingest.call_args.args
        assert source == 'document:' + folder + '/report.CSV'
        assert records[0]['filename'] == records[0]['source_name'] == result.filename
        assert records[0]['file_format'] == 'csv' and records[0]['row_number'] == 2
    assert ingest.call_args_list[0].args[0] != ingest.call_args_list[1].args[0]


async def test_folder_duplicate_checks_exact_relative_source_and_cleans_temporary_file(monkeypatch, tmp_path):
    import hashlib
    query = []
    raw = b'name,value\nsensor,247'
    path = 'Knowledge/subfolder/report.csv'
    def existing(digest, filename):
        query.append((digest, filename))
        return {'filename': path}
    monkeypatch.setattr(documents.qdrant_service, 'get_sample_by_content_hash', existing)
    ingest = AsyncMock()
    monkeypatch.setattr(documents, 'ingest', ingest)
    result = await documents.upload_document(UploadFile(filename='report.csv', file=io.BytesIO(raw)), relative_path=path)
    assert query == [(hashlib.sha256(raw).hexdigest(), path)]
    assert result.skipped_duplicate
    ingest.assert_not_awaited()
    assert not list(tmp_path.rglob('*.csv'))


@pytest.mark.parametrize('path', ['../report.csv','/tmp/report.csv','C:\\data\\report.csv','Folder/../report.csv','Folder//report.csv','Folder/./report.csv','Folder/other.csv','report.csv','Folder/\x00/report.csv'])
async def test_invalid_relative_folder_paths_rejected_before_writing(path, tmp_path):
    file = UploadFile(filename='report.csv', file=io.BytesIO(b'a,b\n1,2'))
    with pytest.raises(HTTPException) as exc:
        await documents.upload_document(file, relative_path=path)
    assert exc.value.status_code == 400 and file.file.closed
    assert not list(tmp_path.rglob('*.csv'))


async def test_windows_relative_path_is_normalized(monkeypatch):
    ingest = AsyncMock()
    monkeypatch.setattr(documents, 'ingest', ingest)
    result = await documents.upload_document(UploadFile(filename='sample.csv', file=io.BytesIO(b'a,b\n1,2')), relative_path='Knowledge\\Sub\\sample.csv')
    assert result.filename == 'Knowledge/Sub/sample.csv'


async def test_document_formats_matches_backend_limits_and_folder_form_contract(monkeypatch):
    import httpx
    from app.main import app
    monkeypatch.setattr(settings, 'APP_ENV', 'local')
    monkeypatch.setattr(settings, 'API_KEYS', {})
    monkeypatch.setattr(app, 'middleware_stack', None)
    monkeypatch.setattr(documents, 'ingest', AsyncMock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        formats = (await client.get('/api/documents/formats')).json()
        assert set(formats['extensions']) == documents.SUPPORTED_EXTENSIONS
        assert formats['max_upload_bytes'] == settings.MAX_UPLOAD_BYTES
        response = await client.post('/api/documents/upload', files={'file':('report.csv', b'a,b\n1,2', 'text/csv')}, data={'relative_path':'Knowledge/Sub/report.csv'})
        assert response.status_code == 200 and response.json()['filename'] == 'Knowledge/Sub/report.csv'
        too_long = await client.post('/api/documents/upload', files={'file':('report.csv', b'a,b\n1,2', 'text/csv')}, data={'relative_path':'Knowledge/'+'x'*1024+'/report.csv'})
        assert too_long.status_code == 422


def test_hash_lookup_can_constrain_filename_without_changing_legacy_behavior(monkeypatch):
    filters = []
    monkeypatch.setattr(documents.qdrant_service, '_scroll_one_by_filter', lambda value: filters.append(value))
    type(documents.qdrant_service).get_sample_by_content_hash(documents.qdrant_service, 'digest', 'Knowledge/Sub/report.csv')
    assert [(condition.key, condition.match.value) for condition in filters[0].must] == [('content_hash','digest'),('filename','Knowledge/Sub/report.csv')]
    type(documents.qdrant_service).get_sample_by_content_hash(documents.qdrant_service, 'digest')
    assert len(filters[1].must) == 1
