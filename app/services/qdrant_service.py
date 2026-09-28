from uuid import uuid4
import re
import threading

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
    MatchAny,
    IsEmptyCondition,
    PayloadField,
    PayloadSchemaType,
)

from app.core.config import settings
from app.core.security import tenant_context
from app.services import index_manifest


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=15, check_compatibility=False)
        self.collection_name = settings.QDRANT_COLLECTION
        self._schema_lock = threading.Lock()
        self._indexed_collections = set()

    @property
    def collection_name(self):
        tenant = tenant_context.get()
        return self._base_collection if tenant == "local" and settings.APP_ENV == "local" else f"{self._base_collection}__{tenant}"

    @collection_name.setter
    def collection_name(self, value):
        self._base_collection = value

    def active_filter(self, active_versions=None):
        active_versions = index_manifest.versions() if active_versions is None else active_versions
        conditions = [FieldCondition(key="version", match=MatchAny(any=active_versions or ["__none__"]))]
        if settings.APP_ENV == "local" and tenant_context.get() == "local":
            conditions.append(IsEmptyCondition(is_empty=PayloadField(key="version")))
        return Filter(should=conditions)

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
            scroll_filter=Filter(must=[payload_filter, self.active_filter()]),
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
        with self._schema_lock:
            self._ensure_collection(vector_size)

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_exists():
            config = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(config, VectorParams) or config.size != vector_size:
                raise ValueError("Embedding dimension mismatch; reindex into a new collection")
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    def upsert_batch(self, vectors: list[list[float]], records: list[dict], version: str):
        if not records or len(vectors) != len(records):
            raise ValueError("Invalid embedding batch")
        self.ensure_collection(len(vectors[0]))
        with self._schema_lock:
            if self.collection_name not in self._indexed_collections:
                for field in ("version", "content_hash", "filename"):
                    self.client.create_payload_index(self.collection_name, field, PayloadSchemaType.KEYWORD, wait=True)
                self._indexed_collections.add(self.collection_name)
        self.client.upsert(self.collection_name, points=[
            PointStruct(id=item["id"], vector=vector, payload={**item, "version": version})
            for vector, item in zip(vectors, records)
        ], wait=True)

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
        active_versions: list[str] | None = None,
    ) -> list[dict]:
        self.ensure_collection(vector_size=len(query_vector))

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=self.active_filter(active_versions),
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
        required = {token.lower() for token in required_tokens}
        if not required:
            return []
        candidates = index_manifest.lexical(" ".join(required_tokens), max(limit * 5, 100))
        return [item for item in candidates
                if required.issubset(set(re.findall(r"\w+", item["text"].lower())))][:limit]


qdrant_service = QdrantService()
