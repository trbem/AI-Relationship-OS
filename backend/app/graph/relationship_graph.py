from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Message,
    Person,
    PersonMemory,
    Relationship,
    RelationshipEvent,
)


class RelationshipGraphService:
    def build_snapshot(self, db: Session, user_id: str, days: int | None = None) -> dict:
        people = db.query(Person).filter(Person.user_id == user_id).all()
        relationships = {item.person_id: item for item in db.query(Relationship).filter(Relationship.user_id == user_id).all()}
        active_window_days = days or 30

        center_node = {
            "id": "user",
            "name": "我",
            "type": "center",
            "group": "self",
            "weight": 100.0,
            "emotion": "neutral",
            "intimacy": 1.0,
            "interaction": 0,
            "trust": 1.0,
            "recent_active": True,
            "active_score": 1.0,
            "relationship_score": 100.0,
            "hint": "你的关系地图中心节点。",
        }

        nodes = [center_node]
        links: list[dict] = []
        group_nodes: dict[str, dict] = {}
        changes: list[str] = []
        strongest_tie: tuple[str | None, float] = (None, -1.0)
        stress_count = 0
        active_count = 0

        for person in people:
            group_name = self._infer_group(person)
            if group_name not in group_nodes:
                group_nodes[group_name] = {
                    "id": f"group:{group_name}",
                    "name": group_name,
                    "type": "group",
                    "group": group_name,
                    "weight": 60.0,
                    "emotion": "neutral",
                    "intimacy": 0.5,
                    "interaction": 0,
                    "trust": 0.5,
                    "recent_active": False,
                    "active_score": 0.0,
                    "relationship_score": 50.0,
                    "hint": f"{group_name} 关系分组",
                }

            relationship = relationships.get(person.id)
            messages = self._filtered_messages(person.messages, days)
            memories = self._filtered_memories(person.memories, days)
            events = self._filtered_events(
                db.query(RelationshipEvent)
                .filter(RelationshipEvent.person_id == person.id)
                .all(),
                days,
            )

            interaction = len(messages)
            recent_interaction = self._count_recent_messages(messages, days=min(active_window_days, 7))
            activity_ratio = min(recent_interaction / 20.0, 1.0)
            trust = relationship.trust if relationship else min(0.35 + interaction * 0.01, 0.95)
            frequency = relationship.frequency if relationship else min(interaction / max(active_window_days * 3, 1), 1.0)
            score = relationship.score if relationship else min(0.4 + interaction * 0.01, 1.0)
            memory_importance = self._average_memory_importance(memories)
            emotion = self._infer_emotion(memories)
            intimacy = min((trust * 0.5) + (frequency * 0.3) + (memory_importance * 0.2), 1.0)
            event_impact = self._event_impact(events)
            evidence_coverage = min(
                1.0,
                len(
                    {
                        message_id
                        for event in events
                        for link in event.evidence_links
                        for message_id in [link.message_id]
                    }
                )
                / max(interaction, 1),
            )
            recency = min(1.0, recent_interaction / max(interaction, 1) * 3)
            score_components = {
                "base": round(score * 0.30, 4),
                "frequency": round(frequency * 0.20, 4),
                "recency": round(recency * 0.15, 4),
                "event_impact": round(event_impact * 0.20, 4),
                "memory_importance": round(memory_importance * 0.10, 4),
                "evidence_coverage": round(evidence_coverage * 0.05, 4),
            }
            normalized_score = min(1.0, max(0.0, sum(score_components.values())))
            weight = round(30 + normalized_score * 70, 2)
            relationship_score = round(min(100.0, weight), 1)
            hint = self._build_hint(emotion, recent_interaction, trust)
            recent_active = recent_interaction > 0

            if recent_active:
                active_count += 1
            if emotion == "stress":
                stress_count += 1
            if relationship_score > strongest_tie[1]:
                strongest_tie = (person.name, relationship_score)

            change = self._describe_change(person.name, recent_interaction, interaction)
            if change:
                changes.append(change)

            nodes.append(
                {
                    "id": person.id,
                    "name": person.name,
                    "type": "person",
                    "group": group_name,
                    "weight": weight,
                    "emotion": emotion,
                    "intimacy": round(intimacy, 3),
                    "interaction": interaction,
                    "trust": round(trust, 3),
                    "recent_active": recent_active,
                    "active_score": round(activity_ratio, 3),
                    "relationship_score": relationship_score,
                    "hint": hint,
                    "score_components": score_components,
                    "change_reasons": self._change_reasons(
                        recent_interaction, event_impact, memory_importance, evidence_coverage
                    ),
                }
            )

            links.append(
                {
                    "source": "user",
                    "target": person.id,
                    "strength": round(intimacy, 3),
                    "interaction": interaction,
                    "emotion": emotion,
                    "width": round(1 + min(interaction / 20.0, 5.0), 2),
                }
            )
            links.append(
                {
                    "source": f"group:{group_name}",
                    "target": person.id,
                    "strength": round(max(0.25, intimacy * 0.7), 3),
                    "interaction": interaction,
                    "emotion": emotion,
                    "width": round(1 + min(interaction / 30.0, 4.0), 2),
                }
            )

            group_nodes[group_name]["interaction"] += interaction
            group_nodes[group_name]["weight"] += weight * 0.1
            group_nodes[group_name]["active_score"] = max(group_nodes[group_name]["active_score"], activity_ratio)
            group_nodes[group_name]["recent_active"] = group_nodes[group_name]["recent_active"] or recent_active

        nodes.extend(group_nodes.values())
        insights = {
            "top_changes": changes[:5],
            "active_count": active_count,
            "strongest_tie": strongest_tie[0],
            "stress_count": stress_count,
        }
        return {"nodes": nodes, "links": links, "insights": insights}

    def build_timeline(self, db: Session, user_id: str, checkpoints: list[int]) -> dict:
        checkpoints_sorted = sorted(set(checkpoints))
        series: list[dict] = []

        for days in checkpoints_sorted:
            snapshot = self.build_snapshot(db, user_id, days=days)
            person_nodes = [n for n in snapshot["nodes"] if n["type"] == "person"]
            timeline_nodes = []
            for node in person_nodes:
                node_copy = dict(node)
                node_copy["days_ago"] = days
                node_copy["snapshot_key"] = f"{node['id']}@{days}"
                timeline_nodes.append(node_copy)
            series.append({
                "days": days,
                "label": self._checkpoint_label(days),
                "nodes": timeline_nodes,
                "insights": snapshot["insights"],
            })

        return {"series": series, "checkpoints": checkpoints_sorted}

    def _checkpoint_label(self, days: int) -> str:
        if days <= 7:
            return "近7天"
        if days <= 30:
            return "近30天"
        if days <= 90:
            return "近3个月"
        if days <= 180:
            return "近半年"
        return f"{days}天"

    def _infer_group(self, person: Person) -> str:
        text = f"{person.name} {person.profile_summary or ''}".lower()
        if any(keyword in text for keyword in ["妈", "爸", "family", "家"]):
            return "家庭"
        if any(keyword in text for keyword in ["总", "客户", "项目", "work", "老板"]):
            return "工作"
        if any(keyword in text for keyword in ["朋友", "同学", "兄弟", "friend"]):
            return "朋友"
        return "未分类"

    def _filtered_messages(self, messages: list[Message], days: int | None) -> list[Message]:
        ordered = sorted(messages, key=lambda item: item.sent_at or item.created_at)
        if days is None:
            return ordered
        threshold = datetime.utcnow() - timedelta(days=days)
        return [message for message in ordered if (message.sent_at or message.created_at) >= threshold]

    def _filtered_memories(self, memories: list[PersonMemory], days: int | None) -> list[PersonMemory]:
        ordered = sorted(memories, key=lambda item: item.timestamp or item.created_at)
        if days is None:
            return ordered
        threshold = datetime.utcnow() - timedelta(days=days)
        return [memory for memory in ordered if (memory.timestamp or memory.created_at) >= threshold]

    def _filtered_events(
        self, events: list[RelationshipEvent], days: int | None
    ) -> list[RelationshipEvent]:
        ordered = sorted(events, key=lambda item: item.occurred_at or item.created_at)
        if days is None:
            return ordered
        threshold = datetime.utcnow() - timedelta(days=days)
        return [
            event
            for event in ordered
            if (event.occurred_at or event.created_at) >= threshold
        ]

    def _event_impact(self, events: list[RelationshipEvent]) -> float:
        if not events:
            return 0.5
        signed = 0.0
        for event in events:
            direction = 1 if event.impact_direction == "positive" else -1 if event.impact_direction == "negative" else 0
            signed += direction * event.impact_strength * event.confidence
        return min(1.0, max(0.0, 0.5 + signed / max(len(events), 1) * 0.5))

    def _change_reasons(
        self,
        recent_interaction: int,
        event_impact: float,
        memory_importance: float,
        evidence_coverage: float,
    ) -> list[str]:
        reasons = []
        reasons.append(
            "Recent interaction is active."
            if recent_interaction > 0
            else "No interaction was found in the recent window."
        )
        if event_impact > 0.6:
            reasons.append("Recent relationship events contribute positively.")
        elif event_impact < 0.4:
            reasons.append("Recent relationship events contribute negatively.")
        if memory_importance >= 0.7:
            reasons.append("High-importance memories materially affect the score.")
        if evidence_coverage < 0.2:
            reasons.append("Evidence coverage is limited, so this score is less certain.")
        return reasons

    def build_knowledge_map(
        self,
        db: Session,
        user_id: str,
        *,
        days: int | None = 30,
        person_id: str | None = None,
        event_types: set[str] | None = None,
        min_confidence: float = 0.5,
    ) -> dict:
        snapshot = self.build_snapshot(db, user_id, days=days)
        nodes = [
            {**node, "node_type": node["type"], "occurred_at": None}
            for node in snapshot["nodes"]
            if person_id is None or node["id"] in {"user", person_id} or node["type"] == "group"
        ]
        node_ids = {node["id"] for node in nodes}
        links = [
            {**link, "id": f"{link['source']}:{link['target']}", "relation_type": "relationship"}
            for link in snapshot["links"]
            if link["source"] in node_ids and link["target"] in node_ids
        ]
        query = db.query(RelationshipEvent).filter(
            RelationshipEvent.user_id == user_id,
            RelationshipEvent.confidence >= min_confidence,
        )
        if person_id:
            query = query.filter(RelationshipEvent.person_id == person_id)
        if event_types:
            query = query.filter(RelationshipEvent.event_type.in_(event_types))
        events = self._filtered_events(query.all(), days)
        for event in events:
            event_node_id = f"event:{event.id}"
            nodes.append(
                {
                    "id": event_node_id,
                    "name": event.title,
                    "type": "event",
                    "node_type": "event",
                    "group": event.event_type,
                    "weight": 22 + event.impact_strength * 18,
                    "emotion": event.emotion,
                    "relationship_score": event.impact_strength * 100,
                    "confidence": event.confidence,
                    "summary": event.summary,
                    "occurred_at": (event.occurred_at or event.created_at).isoformat(),
                    "evidence_message_ids": [link.message_id for link in event.evidence_links],
                }
            )
            links.append(
                {
                    "id": f"{event.person_id}:{event_node_id}",
                    "source": event.person_id,
                    "target": event_node_id,
                    "relation_type": event.event_type,
                    "strength": event.confidence,
                    "width": 1 + event.impact_strength * 3,
                    "emotion": event.emotion,
                    "interaction": len(event.evidence_links),
                }
            )
        return {"nodes": nodes, "links": links, "insights": snapshot["insights"]}

    def _count_recent_messages(self, messages: list[Message], days: int) -> int:
        threshold = datetime.utcnow() - timedelta(days=days)
        return sum(1 for message in messages if (message.sent_at or message.created_at) >= threshold)

    def _average_memory_importance(self, memories: list[PersonMemory]) -> float:
        if not memories:
            return 0.3
        return min(sum(memory.importance for memory in memories) / len(memories), 1.0)

    def _infer_emotion(self, memories: list[PersonMemory]) -> str:
        if not memories:
            return "neutral"
        counter = Counter(memory.emotion.lower() for memory in memories[-5:])
        most_common = counter.most_common(1)[0][0]
        if most_common in {"stress", "anxious", "angry", "sad"}:
            return "stress"
        if most_common in {"happy", "excited", "supportive", "warm"}:
            return "positive"
        return "neutral"

    def _build_hint(self, emotion: str, recent_interaction: int, trust: float) -> str:
        if emotion == "stress":
            return "最近压力偏高，沟通建议先说结果。"
        if recent_interaction > 10:
            return "最近互动频繁，适合主动推进关系。"
        if trust > 0.75:
            return "信任基础较强，可以进行更直接沟通。"
        return "维持稳定互动，逐步增强信任。"

    def _describe_change(self, name: str, recent_interaction: int, total_interaction: int) -> str | None:
        if total_interaction == 0:
            return None
        ratio = recent_interaction / total_interaction
        if ratio >= 0.3 and recent_interaction > 0:
            return f"{name} 近7天互动明显增加"
        if recent_interaction == 0:
            return f"{name} 近期互动下降，建议关注"
        return f"{name} 保持稳定联系"
