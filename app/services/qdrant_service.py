from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION

    def _collection_exists(self) -> bool:
        collection_names = [
            collection.name
            for collection in self.client.get_collections().collections
        ]
        return self.collection_name in collection_names

    def _scroll_one_by_filter(self, payload_filter: Filter) -> dict | None:
        if not self._collection_exists():
            return None

        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=payload_filter,
            limit=1,
            with_payload=True,
            with_vectors=False,
        )

        if not records:
            return None

        record = records[0]
        payload = record.payload or {}
        return self._payload_to_item(record.id, payload, score=1.0)

    def exists_by_content_hash(self, content_hash: str) -> bool:
        payload_filter = Filter(
            must=[
                FieldCondition(
                    key="content_hash",
                    match=MatchValue(value=content_hash),
                )
            ]
        )
        return self._scroll_one_by_filter(payload_filter) is not None

    def get_sample_by_content_hash(self, content_hash: str) -> dict | None:
        payload_filter = Filter(
            must=[
                FieldCondition(
                    key="content_hash",
                    match=MatchValue(value=content_hash),
                )
            ]
        )
        return self._scroll_one_by_filter(payload_filter)

    def delete_by_filename(self, filename: str) -> None:
        if not self._collection_exists():
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="filename",
                            match=MatchValue(value=filename),
                        )
                    ]
                )
            ),
        )

    def ensure_collection(self, vector_size: int) -> None:
        if self._collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    def upsert_text(
        self,
        vector: list[float],
        text: str,
        source_name: str | None = None,
        metadata: dict | None = None,
        point_id: str | None = None,
    ) -> str:
        self.ensure_collection(vector_size=len(vector))

        resolved_point_id = point_id or str(uuid4())

        payload = {
            "text": text,
            "source_name": source_name,
        }

        if metadata:
            payload.update(metadata)

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=resolved_point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

        return resolved_point_id

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        self.ensure_collection(vector_size=len(query_vector))

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        items = []

        for result in response.points:
            payload = result.payload or {}

            items.append(self._payload_to_item(
                result.id,
                payload,
                result.score,
            ))

        return items

    def _payload_to_item(self, point_id: object, payload: dict, score: float) -> dict:
        return {
            "id": str(point_id),
            "score": score,
            "text": payload.get("text", ""),
            "source_name": payload.get("source_name"),
            "source_type": payload.get("source_type"),
            "filename": payload.get("filename"),
            "page_number": payload.get("page_number"),
            "chunk_index": payload.get("chunk_index"),
            "file_format": payload.get("file_format"),
            "sheet_name": payload.get("sheet_name"),
            "row_number": payload.get("row_number"),
            "database": payload.get("database"),
            "schema_name": payload.get("schema_name"),
            "table_name": payload.get("table_name"),
            "row_key": payload.get("row_key"),
            "content_hash": payload.get("content_hash"),
            "saved_path": payload.get("saved_path"),
        }

    def search_by_required_tokens(
        self,
        required_tokens: list[str],
        *,
        limit: int = 20,
    ) -> list[dict]:
        if not required_tokens:
            return []

        if not self._collection_exists():
            return []

        required_lower = [token.lower() for token in required_tokens]
        matched: list[dict] = []
        offset = None

        while len(matched) < limit:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not records:
                break

            for record in records:
                payload = record.payload or {}
                searchable = " ".join([
                    payload.get("text") or "",
                    payload.get("source_name") or "",
                    payload.get("table_name") or "",
                ]).lower()

                if all(token in searchable for token in required_lower):
                    matched.append(
                        self._payload_to_item(record.id, payload, score=0.99)
                    )

                    if len(matched) >= limit:
                        break

            if offset is None:
                break

        return matched


qdrant_service = QdrantService()
