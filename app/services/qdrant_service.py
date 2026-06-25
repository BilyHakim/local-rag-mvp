from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION

    def ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        collection_names = [collection.name for collection in collections]

        if self.collection_name in collection_names:
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
    ) -> str:
        self.ensure_collection(vector_size=len(vector))

        point_id = str(uuid4())

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
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

        return point_id

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

            items.append({
                "id": str(result.id),
                "score": result.score,
                "text": payload.get("text", ""),
                "source_name": payload.get("source_name"),
                "source_type": payload.get("source_type"),
                "filename": payload.get("filename"),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index"),
                "file_format": payload.get("file_format"),
                "sheet_name": payload.get("sheet_name"),
                "row_number": payload.get("row_number"),
            })

        return items


qdrant_service = QdrantService()
