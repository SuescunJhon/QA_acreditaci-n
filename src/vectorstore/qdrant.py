import uuid
import warnings
from dataclasses import dataclass

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.config.settings import Settings


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID | None
    document_name: str
    text: str
    page_start: int | None
    page_end: int | None
    chunk_type: str | None
    score: float | None


def create_qdrant_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    if settings.qdrant_path:
        return QdrantClient(path=settings.qdrant_path)
    return QdrantClient(":memory:")


def _document_filter(document_id: uuid.UUID) -> Filter:
    return Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=str(document_id)))])


class QdrantRepository:
    def __init__(self, client: QdrantClient, collection: str, dimension: int):
        self.client = client
        self.collection = collection
        self.dimension = dimension

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            self.collection,
            vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
        )
        with warnings.catch_warnings():  # el Qdrant local (tests/modo embebido) ignora los índices
            warnings.simplefilter("ignore", UserWarning)
            self.client.create_payload_index(
                self.collection, field_name="document_id", field_schema=PayloadSchemaType.KEYWORD
            )

    @staticmethod
    def _point_id(document_id: uuid.UUID, index: int) -> str:
        return str(uuid.uuid5(document_id, f"chunk-{index}"))

    @staticmethod
    def _payload(document_id: uuid.UUID, doc: Document) -> dict:
        meta = doc.metadata
        page_start = meta.get("pagina_inicio", meta.get("pagina"))
        page_end = meta.get("pagina_fin", meta.get("pagina"))
        return {
            **meta,
            "page_content": doc.page_content,
            "document_id": str(document_id),
            "pagina_inicio": page_start,
            "pagina_fin": page_end,
        }

    def upsert_document(
        self, document_id: uuid.UUID, documents: list[Document], vectors: list[list[float]]
    ) -> int:
        if len(documents) != len(vectors):
            raise ValueError("Hay distinto número de fragmentos y de vectores.")
        self.ensure_collection()
        points = [
            PointStruct(
                id=self._point_id(document_id, i),
                vector=vector,
                payload=self._payload(document_id, doc),
            )
            for i, (doc, vector) in enumerate(zip(documents, vectors))
        ]
        for start in range(0, len(points), 256):
            self.client.upsert(self.collection, points[start : start + 256], wait=True)
        return len(points)

    def search(self, vector: list[float], k: int) -> list[RetrievedChunk]:
        if not self.client.collection_exists(self.collection):
            return []
        result = self.client.query_points(
            self.collection, query=vector, limit=k, with_payload=True
        )
        chunks = []
        for point in result.points:
            payload = point.payload or {}
            raw_id = payload.get("document_id")
            chunks.append(
                RetrievedChunk(
                    document_id=uuid.UUID(raw_id) if raw_id else None,
                    document_name=payload.get("fuente", "desconocido"),
                    text=payload.get("page_content", ""),
                    page_start=payload.get("pagina_inicio"),
                    page_end=payload.get("pagina_fin"),
                    chunk_type=payload.get("tipo"),
                    score=point.score,
                )
            )
        return chunks

    def delete_document(self, document_id: uuid.UUID) -> None:
        if not self.client.collection_exists(self.collection):
            return
        self.client.delete(
            self.collection,
            points_selector=FilterSelector(filter=_document_filter(document_id)),
            wait=True,
        )

    def count_document(self, document_id: uuid.UUID) -> int:
        if not self.client.collection_exists(self.collection):
            return 0
        return self.client.count(
            self.collection, count_filter=_document_filter(document_id), exact=True
        ).count
