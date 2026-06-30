from app.services.dedup_service import (
    compute_content_hash,
    compute_text_hash,
    document_point_id,
    knowledge_point_id,
)


def test_compute_content_hash_is_stable():
    content = b"hello world"
    assert compute_content_hash(content) == compute_content_hash(content)
    assert len(compute_content_hash(content)) == 64


def test_compute_content_hash_differs_for_different_content():
    assert compute_content_hash(b"a") != compute_content_hash(b"b")


def test_compute_text_hash_depends_on_source_name():
    text = "same text"
    assert compute_text_hash(text, "a") != compute_text_hash(text, "b")


def test_document_point_id_is_stable():
    content_hash = compute_content_hash(b"doc")
    first = document_point_id(
        content_hash,
        page_number=1,
        chunk_index=0,
        row_number=2,
        sheet_name="Sheet1",
    )
    second = document_point_id(
        content_hash,
        page_number=1,
        chunk_index=0,
        row_number=2,
        sheet_name="Sheet1",
    )
    assert first == second


def test_document_point_id_changes_when_chunk_changes():
    content_hash = compute_content_hash(b"doc")
    first = document_point_id(content_hash, page_number=1, chunk_index=0)
    second = document_point_id(content_hash, page_number=1, chunk_index=1)
    assert first != second


def test_knowledge_point_id_is_stable():
    content_hash = compute_text_hash("manual fact", "source-a")
    assert knowledge_point_id(content_hash) == knowledge_point_id(content_hash)
