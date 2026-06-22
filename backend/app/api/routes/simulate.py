import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import (
    CommunicationScenario,
    Person,
    SimulationEvidence,
    SimulationLog,
    SimulationMessage,
    SimulationSession,
    User,
)
from app.services.simulation_engine import SimulationEngine

router = APIRouter()


class RunRequest(BaseModel):
    person_id: str
    question: str = Field(min_length=1, max_length=5000)


class CreateSessionRequest(RunRequest):
    title: str | None = Field(default=None, max_length=255)


class SessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class ScenarioRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    wording: str = Field(min_length=1, max_length=5000)
    timing: str | None = Field(default=None, max_length=255)
    channel: str | None = Field(default=None, max_length=64)
    goal: str | None = Field(default=None, max_length=2000)
    context: str | None = Field(default=None, max_length=3000)


def _person(db: Session, person_id: str, user_id: str) -> Person:
    person = db.get(Person, person_id)
    if not person or person.user_id != user_id:
        raise HTTPException(status_code=404, detail="person not found")
    if not person.messages:
        raise HTTPException(status_code=400, detail="no messages available for this person")
    return person


def _session(db: Session, session_id: str, user_id: str) -> SimulationSession:
    session = db.get(SimulationSession, session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="simulation session not found")
    return session


def _save_result(
    db: Session,
    session: SimulationSession,
    result: dict,
) -> SimulationMessage:
    assistant = SimulationMessage(
        session_id=session.id,
        role="assistant",
        kind="simulation_result",
        content=result["prediction"][0]["text"] if result["prediction"] else "",
        payload_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(assistant)
    db.flush()
    for item in result["evidence"]:
        db.add(
            SimulationEvidence(
                simulation_message_id=assistant.id,
                person_id=item["person_id"],
                source_type=item["type"],
                source_id=item["source_id"],
                excerpt=item["excerpt"],
                occurred_at=(
                    datetime.fromisoformat(item["occurred_at"])
                    if item.get("occurred_at")
                    else None
                ),
                relevance=item["relevance"],
            )
        )
    session.updated_at = datetime.utcnow()
    return assistant


def _message_dict(message: SimulationMessage) -> dict:
    payload = json.loads(message.payload_json) if message.payload_json else None
    return {
        "id": message.id,
        "role": message.role,
        "kind": message.kind,
        "content": message.content,
        "payload": payload,
        "created_at": message.created_at.isoformat(),
    }


def _session_dict(session: SimulationSession, include_messages: bool = False) -> dict:
    value = {
        "id": session.id,
        "person_id": session.person_id,
        "title": session.title,
        "original_question": session.original_question,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
    if include_messages:
        value["messages"] = [
            _message_dict(item)
            for item in sorted(session.messages, key=lambda row: row.created_at)
        ]
        value["scenarios"] = [
            {
                "id": item.id,
                "label": item.label,
                "wording": item.wording,
                "timing": item.timing,
                "channel": item.channel,
                "goal": item.goal,
                "context": item.context,
                "result": json.loads(item.result_json) if item.result_json else None,
            }
            for item in session.scenarios
        ]
    return value


@router.post("")
def simulate(
    request: RunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    person = _person(db, request.person_id, current_user.id)
    result = SimulationEngine().run(db, person, request.question)
    db.add(
        SimulationLog(
            person_id=person.id,
            question=request.question,
            response_json=json.dumps(result, ensure_ascii=False),
        )
    )
    db.commit()
    return result


@router.post("/sessions", status_code=201)
def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    person = _person(db, request.person_id, current_user.id)
    session = SimulationSession(
        user_id=current_user.id,
        person_id=person.id,
        title=request.title or request.question[:80],
        original_question=request.question,
    )
    db.add(session)
    db.flush()
    db.add(
        SimulationMessage(
            session_id=session.id,
            role="user",
            kind="question",
            content=request.question,
        )
    )
    result = SimulationEngine().run(db, person, request.question)
    _save_result(db, session, result)
    db.commit()
    db.refresh(session)
    return _session_dict(session, include_messages=True)


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    sessions = db.scalars(
        select(SimulationSession)
        .where(SimulationSession.user_id == current_user.id)
        .order_by(SimulationSession.updated_at.desc())
    ).all()
    return [_session_dict(item) for item in sessions]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return _session_dict(_session(db, session_id, current_user.id), include_messages=True)


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, session_id, current_user.id)
    if request.title is not None:
        session.title = request.title
    if request.status is not None:
        session.status = request.status
    db.commit()
    return _session_dict(session)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, session_id, current_user.id)
    db.delete(session)
    db.commit()
    return {"status": "deleted", "session_id": session_id}


@router.post("/sessions/{session_id}/messages", status_code=201)
def continue_session(
    session_id: str,
    request: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, session_id, current_user.id)
    person = _person(db, session.person_id, current_user.id)
    db.add(
        SimulationMessage(
            session_id=session.id,
            role="user",
            kind="follow_up",
            content=request.content,
        )
    )
    context = "\n".join(
        f"{item.role}: {item.content[:300]}"
        for item in sorted(session.messages, key=lambda row: row.created_at)[-6:]
    )
    result = SimulationEngine().run(
        db, person, request.content, conversation_context=context
    )
    assistant = _save_result(db, session, result)
    db.commit()
    return _message_dict(assistant)


@router.post("/sessions/{session_id}/scenarios", status_code=201)
def create_scenario(
    session_id: str,
    request: ScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, session_id, current_user.id)
    person = _person(db, session.person_id, current_user.id)
    question = (
        f"Evaluate this communication option. Wording: {request.wording}. "
        f"Timing: {request.timing or 'unspecified'}. "
        f"Channel: {request.channel or 'unspecified'}. "
        f"Goal: {request.goal or session.original_question}. "
        f"Context: {request.context or 'none'}."
    )
    result = SimulationEngine().run(db, person, question)
    scenario = CommunicationScenario(
        session_id=session.id,
        label=request.label,
        wording=request.wording,
        timing=request.timing,
        channel=request.channel,
        goal=request.goal,
        context=request.context,
        result_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(scenario)
    db.commit()
    return {"id": scenario.id, "label": scenario.label, "result": result}


@router.post("/sessions/{session_id}/compare")
def compare_scenarios(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, session_id, current_user.id)
    scenarios = []
    for item in session.scenarios:
        result = json.loads(item.result_json) if item.result_json else {}
        confidence = result.get("confidence_summary", {}).get("score", 0)
        top = (result.get("prediction") or [{}])[0]
        scenarios.append(
            {
                "id": item.id,
                "label": item.label,
                "wording": item.wording,
                "confidence": confidence,
                "most_likely_response": top.get("text"),
                "most_likely_probability": top.get("probability", 0),
                "advantages": top.get("supporting_factors", []),
                "risks": top.get("counter_factors", []),
                "evidence_coverage": result.get("data_coverage", {}),
            }
        )
    return {
        "session_id": session.id,
        "comparison": scenarios,
        "guidance": (
            "Compare trade-offs and evidence coverage; the highest probability is "
            "not a guarantee or a universal best option."
        ),
    }
