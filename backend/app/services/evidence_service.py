from __future__ import annotations

from datetime import datetime, timezone
from math import exp

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, Person, PersonMemory
from app.services.retrieval_service import RetrievalService


class EvidenceService:
    def collect(
        self,
        db: Session,
        person: Person,
        question: str,
        *,
        message_limit: int = 6,
        memory_limit: int = 4,
    ) -> list[dict]:
        messages = list(
            db.scalars(
                select(Message)
                .where(Message.person_id == person.id)
                .order_by(Message.sent_at.desc(), Message.created_at.desc())
            ).all()
        )
        payload = [
            {
                "id": item.id,
                "content": item.content,
                "sent_at": item.sent_at,
                "sender_name": item.sender_name,
            }
            for item in messages
        ]
        scored = RetrievalService().score_messages(question, payload)
        by_id = {item.id: item for item in messages}
        evidence: list[dict] = []
        for item in scored[:message_limit]:
            message = by_id.get(item["id"])
            if not message:
                continue
            evidence.append(
                {
                    "id": f"message:{message.id}",
                    "type": "message",
                    "source_id": message.id,
                    "person_id": person.id,
                    "excerpt": message.content[:280],
                    "sender_name": message.sender_name,
                    "occurred_at": (message.sent_at or message.created_at).isoformat(),
                    "relevance": round(float(item.get("retrieval_score", 0)), 4),
                    "importance": 0.5,
                }
            )

        memories = list(
            db.scalars(
                select(PersonMemory)
                .where(PersonMemory.person_id == person.id)
                .order_by(PersonMemory.importance.desc(), PersonMemory.created_at.desc())
                .limit(memory_limit * 2)
            ).all()
        )
        question_terms = self._terms(question)
        for memory in memories:
            overlap = len(question_terms & self._terms(memory.event))
            lexical = overlap / max(len(question_terms), 1)
            relevance = min(1.0, memory.importance * 0.65 + lexical * 0.35)
            evidence.append(
                {
                    "id": f"memory:{memory.id}",
                    "type": "memory",
                    "source_id": memory.id,
                    "person_id": person.id,
                    "excerpt": memory.event[:280],
                    "sender_name": None,
                    "occurred_at": (memory.timestamp or memory.created_at).isoformat(),
                    "relevance": round(relevance, 4),
                    "importance": round(memory.importance, 4),
                    "emotion": memory.emotion,
                    "source_message_ids": list(
                        filter(None, (memory.source_message_ids or "").split(","))
                    ),
                }
            )
        evidence.sort(
            key=lambda item: (
                item["relevance"],
                item.get("importance", 0),
                item["occurred_at"] or "",
            ),
            reverse=True,
        )
        return evidence[: message_limit + memory_limit]

    def confidence(self, evidence: list[dict], total_messages: int) -> dict:
        if not evidence:
            return {
                "score": 0.18,
                "level": "low",
                "evidence_strength": "weak",
                "sample_coverage": 0.0,
                "recency": 0.0,
                "relevance": 0.0,
                "consistency": 0.5,
                "explanation": "No directly relevant historical evidence was found.",
            }
        relevance = sum(item["relevance"] for item in evidence) / len(evidence)
        coverage = min(1.0, total_messages / 40.0)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        recencies = []
        for item in evidence:
            try:
                occurred = datetime.fromisoformat(item["occurred_at"]).replace(tzinfo=None)
                recencies.append(exp(-max(0, (now - occurred).days) / 180.0))
            except (TypeError, ValueError):
                recencies.append(0.35)
        recency = sum(recencies) / len(recencies)
        emotions = [
            item.get("emotion")
            for item in evidence
            if item.get("emotion") and item.get("emotion") != "neutral"
        ]
        consistency = 1.0
        if emotions:
            dominant = max(set(emotions), key=emotions.count)
            consistency = emotions.count(dominant) / len(emotions)
        score = min(
            0.92,
            max(
                0.15,
                coverage * 0.30
                + recency * 0.20
                + relevance * 0.35
                + consistency * 0.15,
            ),
        )
        level = "high" if score >= 0.72 else "medium" if score >= 0.45 else "low"
        strength = "strong" if score >= 0.72 else "medium" if score >= 0.45 else "weak"
        return {
            "score": round(score, 4),
            "level": level,
            "evidence_strength": strength,
            "sample_coverage": round(coverage, 4),
            "recency": round(recency, 4),
            "relevance": round(relevance, 4),
            "consistency": round(consistency, 4),
            "explanation": (
                f"Confidence is {level}: {total_messages} messages and "
                f"{len(evidence)} relevant evidence items were considered."
            ),
        }

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
        return {token for token in normalized.split() if len(token) > 1}
