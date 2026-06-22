import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CommunicationScenario,
    GroupSimulation,
    GroupSimulationRound,
    Message,
    MessageVector,
    ImportTask,
    PersonaWorld,
    Person,
    PersonMemory,
    Relationship,
    RelationshipEvent,
    RelationshipEventEvidence,
    SimulationEvidence,
    SimulationLog,
    SimulationMessage,
    SimulationSession,
    StrategyReport,
    User,
    WorldEvent,
    WorldImportTask,
    WorldPersona,
    WorldRelationship,
    WorldSimulation,
    WorldSimulationRound,
    WorldSource,
)

def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _validate_backup_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="备份内容必须是 JSON 对象")
    if payload.get("format") != "relationship-os-backup" or payload.get("version") not in {1, 2, 3}:
        raise HTTPException(status_code=400, detail="不支持的备份格式或版本")
    required = {
        "persons": {"id", "name"},
        "messages": {"id", "sender_name", "content"},
        "memories": {"id", "person_id", "event", "emotion"},
        "vectors": {"id", "message_id", "person_id"},
        "relationships": {"id", "person_id"},
        "simulations": {"id", "person_id", "question", "response_json"},
    }
    for section, keys in required.items():
        rows = payload.get(section, [])
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not keys.issubset(row) for row in rows
        ):
            raise HTTPException(status_code=400, detail=f"备份字段 {section} 无效")
    return payload


def build_user_export(db: Session, user_id: str) -> dict:
    people = db.scalars(select(Person).where(Person.user_id == user_id)).all()
    person_ids = [person.id for person in people]
    messages = db.scalars(select(Message).where(Message.user_id == user_id)).all()
    memories = (
        db.scalars(select(PersonMemory).where(PersonMemory.person_id.in_(person_ids))).all()
        if person_ids
        else []
    )
    vectors = (
        db.scalars(select(MessageVector).where(MessageVector.person_id.in_(person_ids))).all()
        if person_ids
        else []
    )
    relationships = db.scalars(
        select(Relationship).where(Relationship.user_id == user_id)
    ).all()
    simulations = (
        db.scalars(select(SimulationLog).where(SimulationLog.person_id.in_(person_ids))).all()
        if person_ids
        else []
    )
    sessions = db.scalars(
        select(SimulationSession).where(SimulationSession.user_id == user_id)
    ).all()
    session_ids = [item.id for item in sessions]
    simulation_messages = (
        db.scalars(
            select(SimulationMessage).where(
                SimulationMessage.session_id.in_(session_ids)
            )
        ).all()
        if session_ids
        else []
    )
    simulation_message_ids = [item.id for item in simulation_messages]
    simulation_evidence = (
        db.scalars(
            select(SimulationEvidence).where(
                SimulationEvidence.simulation_message_id.in_(simulation_message_ids)
            )
        ).all()
        if simulation_message_ids
        else []
    )
    events = db.scalars(
        select(RelationshipEvent).where(RelationshipEvent.user_id == user_id)
    ).all()
    event_ids = [item.id for item in events]
    event_evidence = (
        db.scalars(
            select(RelationshipEventEvidence).where(
                RelationshipEventEvidence.event_id.in_(event_ids)
            )
        ).all()
        if event_ids
        else []
    )
    scenarios = (
        db.scalars(
            select(CommunicationScenario).where(
                CommunicationScenario.session_id.in_(session_ids)
            )
        ).all()
        if session_ids
        else []
    )
    reports = db.scalars(
        select(StrategyReport).where(StrategyReport.user_id == user_id)
    ).all()
    group_simulations = db.scalars(
        select(GroupSimulation).where(GroupSimulation.user_id == user_id)
    ).all()
    group_ids = [item.id for item in group_simulations]
    group_rounds = (
        db.scalars(
            select(GroupSimulationRound).where(
                GroupSimulationRound.simulation_id.in_(group_ids)
            )
        ).all()
        if group_ids
        else []
    )
    worlds = db.scalars(
        select(PersonaWorld).where(PersonaWorld.user_id == user_id)
    ).all()
    world_ids = [item.id for item in worlds]
    world_personas = (
        db.scalars(select(WorldPersona).where(WorldPersona.world_id.in_(world_ids))).all()
        if world_ids else []
    )
    world_relationships = (
        db.scalars(
            select(WorldRelationship).where(WorldRelationship.world_id.in_(world_ids))
        ).all()
        if world_ids else []
    )
    world_sources = (
        db.scalars(select(WorldSource).where(WorldSource.world_id.in_(world_ids))).all()
        if world_ids else []
    )
    world_import_tasks = db.scalars(
        select(WorldImportTask).where(WorldImportTask.user_id == user_id)
    ).all()
    world_simulations = (
        db.scalars(select(WorldSimulation).where(WorldSimulation.world_id.in_(world_ids))).all()
        if world_ids else []
    )
    world_simulation_ids = [item.id for item in world_simulations]
    world_rounds = (
        db.scalars(
            select(WorldSimulationRound).where(
                WorldSimulationRound.simulation_id.in_(world_simulation_ids)
            )
        ).all()
        if world_simulation_ids else []
    )
    world_events = (
        db.scalars(select(WorldEvent).where(WorldEvent.world_id.in_(world_ids))).all()
        if world_ids else []
    )
    return {
        "format": "relationship-os-backup",
        "version": 3,
        "exported_at": datetime.utcnow().isoformat(),
        "persons": [
            {
                "id": item.id,
                "name": item.name,
                "profile_summary": item.profile_summary,
                "confidence": item.confidence,
                "created_at": _iso(item.created_at),
            }
            for item in people
        ],
        "messages": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "sender_name": item.sender_name,
                "direction": item.direction,
                "content": item.content,
                "sent_at": _iso(item.sent_at),
                "created_at": _iso(item.created_at),
                "fingerprint": item.fingerprint,
            }
            for item in messages
        ],
        "memories": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "event": item.event,
                "emotion": item.emotion,
                "importance": item.importance,
                "source_message_ids": item.source_message_ids,
                "timestamp": _iso(item.timestamp),
                "created_at": _iso(item.created_at),
            }
            for item in memories
        ],
        "vectors": [
            {
                "id": item.id,
                "message_id": item.message_id,
                "person_id": item.person_id,
                "embedding": list(item.embedding) if item.embedding is not None else None,
                "embedding_ref": item.embedding_ref,
                "created_at": _iso(item.created_at),
            }
            for item in vectors
        ],
        "relationships": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "score": item.score,
                "trust": item.trust,
                "frequency": item.frequency,
                "created_at": _iso(item.created_at),
            }
            for item in relationships
        ],
        "simulations": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "question": item.question,
                "response_json": item.response_json,
                "created_at": _iso(item.created_at),
            }
            for item in simulations
        ],
        "simulation_sessions": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "title": item.title,
                "original_question": item.original_question,
                "status": item.status,
                "legacy_log_id": item.legacy_log_id,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in sessions
        ],
        "simulation_messages": [
            {
                "id": item.id,
                "session_id": item.session_id,
                "role": item.role,
                "kind": item.kind,
                "content": item.content,
                "payload_json": item.payload_json,
                "created_at": _iso(item.created_at),
            }
            for item in simulation_messages
        ],
        "simulation_evidence": [
            {
                "id": item.id,
                "simulation_message_id": item.simulation_message_id,
                "person_id": item.person_id,
                "source_type": item.source_type,
                "source_id": item.source_id,
                "excerpt": item.excerpt,
                "occurred_at": _iso(item.occurred_at),
                "relevance": item.relevance,
                "created_at": _iso(item.created_at),
            }
            for item in simulation_evidence
        ],
        "relationship_events": [
            {
                "id": item.id,
                "person_id": item.person_id,
                "event_type": item.event_type,
                "title": item.title,
                "summary": item.summary,
                "emotion": item.emotion,
                "impact_direction": item.impact_direction,
                "impact_strength": item.impact_strength,
                "confidence": item.confidence,
                "occurred_at": _iso(item.occurred_at),
                "source_fingerprint": item.source_fingerprint,
                "extraction_version": item.extraction_version,
                "created_at": _iso(item.created_at),
            }
            for item in events
        ],
        "relationship_event_evidence": [
            {"id": item.id, "event_id": item.event_id, "message_id": item.message_id}
            for item in event_evidence
        ],
        "communication_scenarios": [
            {
                "id": item.id,
                "session_id": item.session_id,
                "label": item.label,
                "wording": item.wording,
                "timing": item.timing,
                "channel": item.channel,
                "goal": item.goal,
                "context": item.context,
                "result_json": item.result_json,
                "created_at": _iso(item.created_at),
            }
            for item in scenarios
        ],
        "strategy_reports": [
            {
                "id": item.id,
                "session_id": item.session_id,
                "title": item.title,
                "status": item.status,
                "content_markdown": item.content_markdown,
                "payload_json": item.payload_json,
                "evidence_snapshot_json": item.evidence_snapshot_json,
                "created_at": _iso(item.created_at),
            }
            for item in reports
        ],
        "group_simulations": [
            {
                "id": item.id,
                "primary_person_id": item.primary_person_id,
                "title": item.title,
                "goal": item.goal,
                "participant_ids_json": item.participant_ids_json,
                "status": item.status,
                "round_count": item.round_count,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in group_simulations
        ],
        "group_simulation_rounds": [
            {
                "id": item.id,
                "simulation_id": item.simulation_id,
                "round_number": item.round_number,
                "state_json": item.state_json,
                "created_at": _iso(item.created_at),
            }
            for item in group_rounds
        ],
        "persona_worlds": [
            {
                "id": item.id,
                "name": item.name,
                "theme": item.theme,
                "world_type": item.world_type,
                "source_type": item.source_type,
                "version": item.version,
                "description": item.description,
                "world_background": item.world_background,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in worlds
        ],
        "world_personas": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "name": item.name,
                "aliases_json": item.aliases_json,
                "summary": item.summary,
                "traits_json": item.traits_json,
                "motivations_json": item.motivations_json,
                "values_json": item.values_json,
                "abilities_json": item.abilities_json,
                "communication_json": item.communication_json,
                "faction": item.faction,
                "background": item.background,
                "avatar_url": item.avatar_url,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "setting_completeness": item.setting_completeness,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in world_personas
        ],
        "world_relationships": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "source_persona_id": item.source_persona_id,
                "target_persona_id": item.target_persona_id,
                "relationship_type": item.relationship_type,
                "directed": item.directed,
                "strength": item.strength,
                "description": item.description,
                "confidence": item.confidence,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "created_at": _iso(item.created_at),
            }
            for item in world_relationships
        ],
        "world_sources": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "persona_id": item.persona_id,
                "relationship_id": item.relationship_id,
                "source_type": item.source_type,
                "external_id": item.external_id,
                "url": item.url,
                "title": item.title,
                "version": item.version,
                "accessed_at": _iso(item.accessed_at),
            }
            for item in world_sources
        ],
        "world_import_tasks": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "query": item.query,
                "status": item.status,
                "stage": item.stage,
                "progress": item.progress,
                "requested_limit": item.requested_limit,
                "result_json": item.result_json,
                "error": item.error,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in world_import_tasks
        ],
        "world_simulations": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "title": item.title,
                "scenario": item.scenario,
                "participant_ids_json": item.participant_ids_json,
                "round_count": item.round_count,
                "status": item.status,
                "setting_completeness": item.setting_completeness,
                "source_coverage": item.source_coverage,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in world_simulations
        ],
        "world_simulation_rounds": [
            {
                "id": item.id,
                "simulation_id": item.simulation_id,
                "round_number": item.round_number,
                "state_json": item.state_json,
                "created_at": _iso(item.created_at),
            }
            for item in world_rounds
        ],
        "world_events": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "title": item.title,
                "summary": item.summary,
                "event_type": item.event_type,
                "is_simulated": item.is_simulated,
                "source_simulation_id": item.source_simulation_id,
                "source_round_number": item.source_round_number,
                "created_at": _iso(item.created_at),
            }
            for item in world_events
        ],
    }


def restore_payload(
    payload: object, db: Session, current_user: User
) -> dict[str, int | str]:
    """Validate and restore a decoded v1-v3 payload in one database transaction."""
    payload = _validate_backup_payload(payload)

    db.execute(delete(WorldImportTask).where(WorldImportTask.user_id == current_user.id))
    old_world_ids = db.scalars(
        select(PersonaWorld.id).where(PersonaWorld.user_id == current_user.id)
    ).all()
    if old_world_ids:
        old_world_simulation_ids = db.scalars(
            select(WorldSimulation.id).where(WorldSimulation.world_id.in_(old_world_ids))
        ).all()
        if old_world_simulation_ids:
            db.execute(
                delete(WorldSimulationRound).where(
                    WorldSimulationRound.simulation_id.in_(old_world_simulation_ids)
                )
            )
        db.execute(delete(WorldEvent).where(WorldEvent.world_id.in_(old_world_ids)))
        db.execute(delete(WorldSimulation).where(WorldSimulation.world_id.in_(old_world_ids)))
        db.execute(delete(WorldSource).where(WorldSource.world_id.in_(old_world_ids)))
        db.execute(
            delete(WorldRelationship).where(WorldRelationship.world_id.in_(old_world_ids))
        )
        db.execute(delete(WorldPersona).where(WorldPersona.world_id.in_(old_world_ids)))
        db.execute(delete(PersonaWorld).where(PersonaWorld.id.in_(old_world_ids)))
    old_person_ids = db.scalars(
        select(Person.id).where(Person.user_id == current_user.id)
    ).all()
    if old_person_ids:
        old_sessions = db.scalars(
            select(SimulationSession.id).where(
                SimulationSession.user_id == current_user.id
            )
        ).all()
        old_group_ids = db.scalars(
            select(GroupSimulation.id).where(GroupSimulation.user_id == current_user.id)
        ).all()
        if old_sessions:
            old_simulation_messages = db.scalars(
                select(SimulationMessage.id).where(
                    SimulationMessage.session_id.in_(old_sessions)
                )
            ).all()
            if old_simulation_messages:
                db.execute(
                    delete(SimulationEvidence).where(
                        SimulationEvidence.simulation_message_id.in_(
                            old_simulation_messages
                        )
                    )
                )
            db.execute(
                delete(CommunicationScenario).where(
                    CommunicationScenario.session_id.in_(old_sessions)
                )
            )
            db.execute(
                delete(StrategyReport).where(
                    StrategyReport.session_id.in_(old_sessions)
                )
            )
            db.execute(
                delete(SimulationMessage).where(
                    SimulationMessage.session_id.in_(old_sessions)
                )
            )
            db.execute(
                delete(SimulationSession).where(SimulationSession.id.in_(old_sessions))
            )
        if old_group_ids:
            db.execute(
                delete(GroupSimulationRound).where(
                    GroupSimulationRound.simulation_id.in_(old_group_ids)
                )
            )
            db.execute(
                delete(GroupSimulation).where(GroupSimulation.id.in_(old_group_ids))
            )
        old_event_ids = db.scalars(
            select(RelationshipEvent.id).where(
                RelationshipEvent.user_id == current_user.id
            )
        ).all()
        if old_event_ids:
            db.execute(
                delete(RelationshipEventEvidence).where(
                    RelationshipEventEvidence.event_id.in_(old_event_ids)
                )
            )
            db.execute(
                delete(RelationshipEvent).where(RelationshipEvent.id.in_(old_event_ids))
            )
        db.execute(delete(SimulationLog).where(SimulationLog.person_id.in_(old_person_ids)))
        db.execute(delete(MessageVector).where(MessageVector.person_id.in_(old_person_ids)))
        db.execute(delete(PersonMemory).where(PersonMemory.person_id.in_(old_person_ids)))
        db.execute(delete(Relationship).where(Relationship.person_id.in_(old_person_ids)))
    db.execute(delete(Message).where(Message.user_id == current_user.id))
    db.execute(delete(ImportTask).where(ImportTask.user_id == current_user.id))
    db.execute(delete(Person).where(Person.user_id == current_user.id))

    for item in payload.get("persons", []):
        db.add(
            Person(
                id=item["id"],
                user_id=current_user.id,
                name=item["name"],
                profile_summary=item.get("profile_summary"),
                confidence=item.get("confidence"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("messages", []):
        db.add(
            Message(
                id=item["id"],
                user_id=current_user.id,
                person_id=item.get("person_id"),
                sender_name=item["sender_name"],
                direction=item.get("direction", "unknown"),
                content=item["content"],
                sent_at=_parse_datetime(item.get("sent_at")),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                fingerprint=item.get("fingerprint"),
            )
        )
    for item in payload.get("memories", []):
        db.add(
            PersonMemory(
                id=item["id"],
                person_id=item["person_id"],
                event=item["event"],
                emotion=item["emotion"],
                importance=item.get("importance", 0.5),
                source_message_ids=item.get("source_message_ids"),
                timestamp=_parse_datetime(item.get("timestamp")),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("vectors", []):
        db.add(
            MessageVector(
                id=item["id"],
                message_id=item["message_id"],
                person_id=item["person_id"],
                embedding=item.get("embedding"),
                embedding_ref=item.get("embedding_ref"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("relationships", []):
        db.add(
            Relationship(
                id=item["id"],
                user_id=current_user.id,
                person_id=item["person_id"],
                score=item.get("score", 0),
                trust=item.get("trust", 0),
                frequency=item.get("frequency", 0),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("simulations", []):
        db.add(
            SimulationLog(
                id=item["id"],
                person_id=item["person_id"],
                question=item["question"],
                response_json=item["response_json"],
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("simulation_sessions", []):
        db.add(
            SimulationSession(
                id=item["id"],
                user_id=current_user.id,
                person_id=item["person_id"],
                title=item["title"],
                original_question=item["original_question"],
                status=item.get("status", "active"),
                legacy_log_id=item.get("legacy_log_id"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("simulation_messages", []):
        db.add(
            SimulationMessage(
                id=item["id"],
                session_id=item["session_id"],
                role=item["role"],
                kind=item.get("kind", "text"),
                content=item["content"],
                payload_json=item.get("payload_json"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("relationship_events", []):
        db.add(
            RelationshipEvent(
                id=item["id"],
                user_id=current_user.id,
                person_id=item["person_id"],
                event_type=item["event_type"],
                title=item["title"],
                summary=item["summary"],
                emotion=item.get("emotion", "neutral"),
                impact_direction=item.get("impact_direction", "neutral"),
                impact_strength=item.get("impact_strength", 0.5),
                confidence=item.get("confidence", 0.5),
                occurred_at=_parse_datetime(item.get("occurred_at")),
                source_fingerprint=item["source_fingerprint"],
                extraction_version=item.get("extraction_version", "rules-v1"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("simulation_evidence", []):
        db.add(
            SimulationEvidence(
                id=item["id"],
                simulation_message_id=item["simulation_message_id"],
                person_id=item["person_id"],
                source_type=item["source_type"],
                source_id=item["source_id"],
                excerpt=item["excerpt"],
                occurred_at=_parse_datetime(item.get("occurred_at")),
                relevance=item.get("relevance", 0),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("relationship_event_evidence", []):
        db.add(
            RelationshipEventEvidence(
                id=item["id"],
                event_id=item["event_id"],
                message_id=item["message_id"],
            )
        )
    for item in payload.get("communication_scenarios", []):
        db.add(
            CommunicationScenario(
                id=item["id"],
                session_id=item["session_id"],
                label=item["label"],
                wording=item["wording"],
                timing=item.get("timing"),
                channel=item.get("channel"),
                goal=item.get("goal"),
                context=item.get("context"),
                result_json=item.get("result_json"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("strategy_reports", []):
        db.add(
            StrategyReport(
                id=item["id"],
                user_id=current_user.id,
                session_id=item["session_id"],
                title=item["title"],
                status=item.get("status", "completed"),
                content_markdown=item["content_markdown"],
                payload_json=item["payload_json"],
                evidence_snapshot_json=item["evidence_snapshot_json"],
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("group_simulations", []):
        db.add(
            GroupSimulation(
                id=item["id"],
                user_id=current_user.id,
                primary_person_id=item["primary_person_id"],
                title=item["title"],
                goal=item["goal"],
                participant_ids_json=item["participant_ids_json"],
                status=item.get("status", "created"),
                round_count=item.get("round_count", 3),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("group_simulation_rounds", []):
        db.add(
            GroupSimulationRound(
                id=item["id"],
                simulation_id=item["simulation_id"],
                round_number=item["round_number"],
                state_json=item["state_json"],
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("persona_worlds", []):
        db.add(
            PersonaWorld(
                id=item["id"],
                user_id=current_user.id,
                name=item["name"],
                theme=item.get("theme"),
                world_type=item.get("world_type", "custom"),
                source_type=item.get("source_type", "manual"),
                version=item.get("version"),
                description=item.get("description"),
                world_background=item.get("world_background"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("world_personas", []):
        db.add(
            WorldPersona(
                id=item["id"],
                world_id=item["world_id"],
                name=item["name"],
                aliases_json=item.get("aliases_json", "[]"),
                summary=item["summary"],
                traits_json=item.get("traits_json", "[]"),
                motivations_json=item.get("motivations_json", "[]"),
                values_json=item.get("values_json", "[]"),
                abilities_json=item.get("abilities_json", "[]"),
                communication_json=item.get("communication_json", "[]"),
                faction=item.get("faction"),
                background=item.get("background"),
                avatar_url=item.get("avatar_url"),
                source_type=item.get("source_type", "manual"),
                source_ref=item.get("source_ref"),
                setting_completeness=item.get("setting_completeness", 0),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("world_relationships", []):
        db.add(
            WorldRelationship(
                id=item["id"],
                world_id=item["world_id"],
                source_persona_id=item["source_persona_id"],
                target_persona_id=item["target_persona_id"],
                relationship_type=item["relationship_type"],
                directed=item.get("directed", True),
                strength=item.get("strength", 0.5),
                description=item.get("description"),
                confidence=item.get("confidence", 0.5),
                source_type=item.get("source_type", "manual"),
                source_ref=item.get("source_ref"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("world_sources", []):
        db.add(
            WorldSource(
                id=item["id"],
                world_id=item["world_id"],
                persona_id=item.get("persona_id"),
                relationship_id=item.get("relationship_id"),
                source_type=item["source_type"],
                external_id=item.get("external_id"),
                url=item["url"],
                title=item.get("title"),
                version=item.get("version"),
                accessed_at=_parse_datetime(item.get("accessed_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("world_import_tasks", []):
        db.add(
            WorldImportTask(
                id=item["id"],
                user_id=current_user.id,
                world_id=item.get("world_id"),
                query=item["query"],
                status=item.get("status", "completed"),
                stage=item.get("stage", "completed"),
                progress=item.get("progress", 1),
                requested_limit=item.get("requested_limit", 20),
                result_json=item.get("result_json", "{}"),
                error=item.get("error"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("world_simulations", []):
        db.add(
            WorldSimulation(
                id=item["id"],
                world_id=item["world_id"],
                user_id=current_user.id,
                title=item["title"],
                scenario=item["scenario"],
                participant_ids_json=item.get("participant_ids_json", "[]"),
                round_count=item.get("round_count", 3),
                status=item.get("status", "completed"),
                setting_completeness=item.get("setting_completeness", 0),
                source_coverage=item.get("source_coverage", 0),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(item.get("updated_at")) or datetime.utcnow(),
            )
        )
    db.flush()
    for item in payload.get("world_simulation_rounds", []):
        db.add(
            WorldSimulationRound(
                id=item["id"],
                simulation_id=item["simulation_id"],
                round_number=item["round_number"],
                state_json=item["state_json"],
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    for item in payload.get("world_events", []):
        db.add(
            WorldEvent(
                id=item["id"],
                world_id=item["world_id"],
                title=item["title"],
                summary=item["summary"],
                event_type=item.get("event_type", "derived"),
                is_simulated=item.get("is_simulated", True),
                source_simulation_id=item.get("source_simulation_id"),
                source_round_number=item.get("source_round_number"),
                created_at=_parse_datetime(item.get("created_at")) or datetime.utcnow(),
            )
        )
    try:
        db.commit()
    except (IntegrityError, KeyError, TypeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="备份数据不完整或存在冲突") from exc
    return {
        "status": "restored",
        "persons": len(payload.get("persons", [])),
        "messages": len(payload.get("messages", [])),
    }
