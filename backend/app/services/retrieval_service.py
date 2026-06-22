from sqlalchemy.orm import Session

from app.models import Message, MessageVector
from app.services.embedding_service import EmbeddingService
from app.vector.pgvector_store import VectorStore


class RetrievalService:
    def score_messages(self, question: str, messages: list[dict]) -> list[dict]:
        embedding_service = EmbeddingService()
        query_vector = embedding_service.build_embedding(question)
        scored: list[tuple[float, dict]] = []

        for item in messages:
            item_vector = embedding_service.build_embedding(item["content"])
            similarity = self._cosine_similarity(query_vector, item_vector)
            scored.append((similarity, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**item, "retrieval_score": round(score, 4)} for score, item in scored[:5] if score > 0]

    def search_by_vector(self, db: Session, query: str, person_id: str | None = None, top_k: int = 5) -> list[dict]:
        embedding_service = EmbeddingService()
        query_vector = embedding_service.build_embedding(query)
        store = VectorStore()
        results = store.search_similar(db, query_vector, person_id=person_id, top_k=top_k)
        output: list[dict] = []
        for vector_row, similarity in results:
            msg = db.get(Message, vector_row.message_id)
            output.append({
                "message_id": vector_row.message_id,
                "content": msg.content if msg else "",
                "score": similarity,
            })
        return output

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)