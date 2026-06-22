from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, RelationshipEvent, RelationshipEventEvidence


@dataclass(frozen=True)
class EventRule:
    event_type: str
    keywords: tuple[str, ...]
    emotion: str
    direction: str
    impact: float


RULES = (
    EventRule("support", ("支持", "帮你", "加油", "support", "help"), "positive", "positive", 0.72),
    EventRule("conflict", ("生气", "争吵", "冲突", "angry", "argue"), "stress", "negative", 0.9),
    EventRule("commitment", ("答应", "保证", "会完成", "promise", "will do"), "positive", "positive", 0.78),
    EventRule("request", ("请", "麻烦", "需要你", "please", "could you"), "neutral", "neutral", 0.55),
    EventRule("rejection", ("拒绝", "不行", "不能", "cannot"), "stress", "negative", 0.72),
    EventRule("apology", ("抱歉", "对不起", "sorry", "apolog"), "mixed", "positive", 0.7),
    EventRule("shared_plan", ("一起", "计划", "安排", "together", "plan"), "positive", "positive", 0.7),
    EventRule("important_change", ("离职", "搬家", "结婚", "分手", "change", "moved"), "mixed", "neutral", 0.82),
)


class RelationshipEventService:
    def extract_incremental(
        self,
        db: Session,
        *,
        user_id: str,
        person_id: str,
        message_ids: list[str],
    ) -> int:
        if not message_ids:
            return 0
        messages = list(
            db.scalars(
                select(Message).where(
                    Message.id.in_(message_ids),
                    Message.user_id == user_id,
                    Message.person_id == person_id,
                )
            ).all()
        )
        created = 0
        for message in messages:
            lowered = message.content.lower()
            for rule in RULES:
                if not any(keyword in lowered for keyword in rule.keywords):
                    continue
                fingerprint = hashlib.sha256(
                    f"{message.id}:{rule.event_type}".encode("utf-8")
                ).hexdigest()
                exists = db.scalar(
                    select(RelationshipEvent.id).where(
                        RelationshipEvent.person_id == person_id,
                        RelationshipEvent.event_type == rule.event_type,
                        RelationshipEvent.source_fingerprint == fingerprint,
                    )
                )
                if exists:
                    continue
                event = RelationshipEvent(
                    user_id=user_id,
                    person_id=person_id,
                    event_type=rule.event_type,
                    title=rule.event_type.replace("_", " ").title(),
                    summary=message.content[:500],
                    emotion=rule.emotion,
                    impact_direction=rule.direction,
                    impact_strength=rule.impact,
                    confidence=0.7,
                    occurred_at=message.sent_at or message.created_at,
                    source_fingerprint=fingerprint,
                )
                db.add(event)
                db.flush()
                db.add(RelationshipEventEvidence(event_id=event.id, message_id=message.id))
                created += 1
                break
        return created

    def remove_message_evidence(self, db: Session, message_id: str) -> None:
        links = list(
            db.scalars(
                select(RelationshipEventEvidence).where(
                    RelationshipEventEvidence.message_id == message_id
                )
            ).all()
        )
        event_ids = {link.event_id for link in links}
        for link in links:
            db.delete(link)
        db.flush()
        for event_id in event_ids:
            has_evidence = db.scalar(
                select(RelationshipEventEvidence.id)
                .where(RelationshipEventEvidence.event_id == event_id)
                .limit(1)
            )
            if not has_evidence:
                event = db.get(RelationshipEvent, event_id)
                if event:
                    db.delete(event)
