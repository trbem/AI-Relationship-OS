import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import (
    GroupSimulation,
    ImportTask,
    Message,
    MessageVector,
    Person,
    PersonMemory,
    Relationship,
    RelationshipEvent,
    SimulationEvidence,
    SimulationLog,
    SimulationSession,
    User,
)
from app.schemas import (
    GeneratePersonRequest,
    MemoryItemResponse,
    PersonDetailResponse,
    PersonaResponse,
    PersonMergeRequest,
    PersonSummaryResponse,
)
from app.services.persona_service import PersonaService

router = APIRouter()


@router.post("/merge")
def merge_persons(
    request: PersonMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    if request.source_person_id == request.target_person_id:
        raise HTTPException(status_code=400, detail="不能合并同一个联系人")
    source = db.get(Person, request.source_person_id)
    target = db.get(Person, request.target_person_id)
    if (
        not source
        or not target
        or source.user_id != current_user.id
        or target.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="联系人不存在")

    target_fingerprints = {
        value
        for value in db.scalars(
            db.query(Message.fingerprint)
            .filter(Message.person_id == target.id, Message.fingerprint.isnot(None))
            .statement
        ).all()
    }
    moved = 0
    for message in list(source.messages):
        if message.fingerprint and message.fingerprint in target_fingerprints:
            db.delete(message)
            continue
        message.person = target
        moved += 1
        if message.fingerprint:
            target_fingerprints.add(message.fingerprint)
    for model in (
        PersonMemory,
        MessageVector,
        SimulationLog,
        SimulationSession,
        SimulationEvidence,
        RelationshipEvent,
    ):
        db.query(model).filter(model.person_id == source.id).update(
            {model.person_id: target.id}, synchronize_session=False
        )
    group_simulations = db.query(GroupSimulation).filter(
        GroupSimulation.user_id == current_user.id
    ).all()
    for group_simulation in group_simulations:
        participant_ids = json.loads(group_simulation.participant_ids_json)
        participant_ids = [
            target.id if item == source.id else item for item in participant_ids
        ]
        group_simulation.participant_ids_json = json.dumps(
            list(dict.fromkeys(participant_ids))
        )
        if group_simulation.primary_person_id == source.id:
            group_simulation.primary_person_id = target.id
    db.query(Relationship).filter(Relationship.person_id == source.id).update(
        {
            Relationship.person_id: target.id,
            Relationship.user_id: current_user.id,
        },
        synchronize_session=False,
    )
    db.query(ImportTask).filter(ImportTask.person_id == source.id).update(
        {ImportTask.person_id: target.id}, synchronize_session=False
    )
    db.delete(source)
    db.commit()
    return {"status": "merged", "target_person_id": target.id, "messages_moved": moved}


@router.get("", response_model=list[PersonSummaryResponse])
def list_persons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonSummaryResponse]:
    people = db.query(Person).where(Person.user_id == current_user.id).all()
    return [
        PersonSummaryResponse(
            id=person.id,
            user_id=person.user_id,
            name=person.name,
            profile_summary=person.profile_summary,
            confidence=person.confidence,
            message_count=len(person.messages),
            memory_count=len(person.memories),
        )
        for person in people
    ]


@router.get("/{person_id}", response_model=PersonDetailResponse)
def get_person(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonDetailResponse:
    person = db.get(Person, person_id)
    if not person or person.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="person not found")

    return PersonDetailResponse(
        id=person.id,
        user_id=person.user_id,
        name=person.name,
        profile_summary=person.profile_summary,
        confidence=person.confidence,
        messages=[message.content for message in person.messages],
        memories=[
            MemoryItemResponse(
                id=memory.id,
                event=memory.event,
                emotion=memory.emotion,
                importance=memory.importance,
                source_message_ids=memory.source_message_ids,
                timestamp=memory.timestamp.isoformat() if memory.timestamp else None,
            )
            for memory in person.memories
        ],
        vector_refs=[vector.embedding_ref or "" for vector in person.vectors],
    )


@router.get("/{person_id}/memories", response_model=list[MemoryItemResponse])
def get_person_memories(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryItemResponse]:
    person = db.get(Person, person_id)
    if not person or person.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="person not found")

    return [
        MemoryItemResponse(
            id=memory.id,
            event=memory.event,
            emotion=memory.emotion,
            importance=memory.importance,
            source_message_ids=memory.source_message_ids,
            timestamp=memory.timestamp.isoformat() if memory.timestamp else None,
        )
        for memory in person.memories
    ]


@router.post("/generate", response_model=PersonaResponse)
def generate_person(
    request: GeneratePersonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonaResponse:
    person = db.get(Person, request.contact_id)
    if not person or person.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="contact_id not found")

    messages = [message.content for message in person.messages]
    if not messages:
        messages = [message.content for message in db.query(Message).filter(Message.person_id == person.id).all()]

    persona = PersonaService().generate_persona(person.name, messages)
    person.profile_summary = persona["evidence_note"]
    person.confidence = persona["confidence"]
    db.commit()
    return PersonaResponse(**{key: value for key, value in persona.items() if key != "system_prompt"})
