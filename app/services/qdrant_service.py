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
            collection = self.client.get_collection(self.collection_name)
            configured_vectors = collection.config.params.vectors
            configured_size = getattr(configured_vectors, "size", None)

            if configured_size is not None and configured_size != vector_size:
                raise RuntimeError(
                    f"Ukuran vector collection '{self.collection_name}' adalah "
                    f"{configured_size}, tetapi embedding menghasilkan {vector_size}. "
                    "Gunakan collection baru atau recreate collection Qdrant."
                )

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
    ) -> str:
        self.ensure_collection(vector_size=len(vector))

        point_id = str(uuid4())

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": text,
                        "source_name": source_name,
                    },
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
            })

        return items


qdrant_service = QdrantService()
