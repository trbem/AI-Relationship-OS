import math

from sqlalchemy import select

from app.models import MessageVector


class VectorStore:
    def upsert_message_vectors(
        self,
        db,
        person_id: str,
        message_ids: list[str],
        embeddings: list[list[float]],
    ) -> list[MessageVector]:
        rows: list[MessageVector] = []
        for message_id, embedding in zip(message_ids, embeddings, strict=False):
            row = MessageVector(
                message_id=message_id,
                person_id=person_id,
                embedding=embedding,
            )
            db.add(row)
            db.flush()
            rows.append(row)
        return rows

    def search_similar(
        self,
        db,
        query_embedding: list[float],
        person_id: str | None = None,
        top_k: int = 5,
    ) -> list[tuple[MessageVector, float]]:
        stmt = select(MessageVector).where(MessageVector.embedding.isnot(None))
        if person_id:
            stmt = stmt.where(MessageVector.person_id == person_id)
        if db.bind.dialect.name == "sqlite":
            rows = db.execute(stmt).scalars().all()
            scored = [
                (row, round(self._cosine_similarity(row.embedding, query_embedding), 4))
                for row in rows
            ]
            scored.sort(key=lambda item: item[1], reverse=True)
            return scored[:top_k]
        stmt = stmt.order_by(MessageVector.embedding.cosine_distance(query_embedding)).limit(top_k)
        result = db.execute(stmt).scalars().all()
        scored: list[tuple[MessageVector, float]] = []
        for row in result:
            scores = db.execute(
                select(MessageVector.embedding.cosine_distance(query_embedding))
                .where(MessageVector.id == row.id)
            ).scalar()
            similarity = 1.0 - float(scores) if scores is not None else 0.0
            scored.append((row, round(similarity, 4)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
