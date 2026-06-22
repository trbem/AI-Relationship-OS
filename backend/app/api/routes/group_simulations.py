import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import (
    GroupSimulation,
    GroupSimulationRound,
    Person,
    User,
)
from app.services.evidence_service import EvidenceService

router = APIRouter()


class GroupRequest(BaseModel):
    primary_person_id: str
    participant_ids: list[str] = Field(min_length=1, max_length=8)
    title: str = Field(min_length=1, max_length=255)
    goal: str = Field(min_length=1, max_length=5000)
    rounds: int = Field(default=3, ge=1, le=5)


def _simulation(db: Session, simulation_id: str, user_id: str) -> GroupSimulation:
    value = db.get(GroupSimulation, simulation_id)
    if not value or value.user_id != user_id:
        raise HTTPException(status_code=404, detail="group simulation not found")
    return value


@router.post("", status_code=201)
def create_group_simulation(
    request: GroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    participant_ids = list(dict.fromkeys(request.participant_ids))
    if request.primary_person_id not in participant_ids:
        participant_ids.insert(0, request.primary_person_id)
    if len(participant_ids) > 8:
        raise HTTPException(status_code=400, detail="at most 8 participants are allowed")
    people = db.query(Person).filter(Person.id.in_(participant_ids)).all()
    if len(people) != len(participant_ids) or any(
        person.user_id != current_user.id for person in people
    ):
        raise HTTPException(status_code=404, detail="one or more participants were not found")
    simulation = GroupSimulation(
        user_id=current_user.id,
        primary_person_id=request.primary_person_id,
        title=request.title,
        goal=request.goal,
        participant_ids_json=json.dumps(participant_ids),
        round_count=request.rounds,
    )
    db.add(simulation)
    db.commit()
    return _dict(simulation)


@router.get("/{simulation_id}")
def get_group_simulation(
    simulation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return _dict(_simulation(db, simulation_id, current_user.id), include_rounds=True)


@router.post("/{simulation_id}/run")
def run_group_simulation(
    simulation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    simulation = _simulation(db, simulation_id, current_user.id)
    participant_ids = json.loads(simulation.participant_ids_json)
    people = {
        person.id: person
        for person in db.query(Person).filter(Person.id.in_(participant_ids)).all()
    }
    db.query(GroupSimulationRound).filter(
        GroupSimulationRound.simulation_id == simulation.id
    ).delete()
    prior_states: dict[str, str] = {}
    for round_number in range(1, simulation.round_count + 1):
        people_states = []
        edges = []
        for index, person_id in enumerate(participant_ids):
            person = people[person_id]
            evidence = EvidenceService().collect(
                db, person, simulation.goal, message_limit=3, memory_limit=2
            )
            confidence = EvidenceService().confidence(evidence, len(person.messages))
            stance = _stance(evidence, round_number, prior_states.get(person_id))
            prior_states[person_id] = stance
            people_states.append(
                {
                    "person_id": person.id,
                    "name": person.name,
                    "stance": stance,
                    "confidence": confidence["score"],
                    "high_uncertainty": confidence["score"] < 0.45,
                    "evidence_ids": [item["id"] for item in evidence],
                    "simulated": True,
                }
            )
            if index:
                source = participant_ids[index - 1]
                edges.append(
                    {
                        "source": source,
                        "target": person_id,
                        "influence": round(0.25 + confidence["score"] * 0.5, 3),
                        "simulated": True,
                    }
                )
        state = {
            "round": round_number,
            "people": people_states,
            "influences": edges,
            "consensus": _consensus(people_states),
            "disclaimer": "Simulated states are not written to relationship history.",
        }
        db.add(
            GroupSimulationRound(
                simulation_id=simulation.id,
                round_number=round_number,
                state_json=json.dumps(state, ensure_ascii=False),
            )
        )
    simulation.status = "completed"
    db.commit()
    return _dict(simulation, include_rounds=True)


@router.get("/{simulation_id}/rounds")
def get_rounds(
    simulation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return _dict(
        _simulation(db, simulation_id, current_user.id), include_rounds=True
    )["rounds"]


def _dict(simulation: GroupSimulation, include_rounds: bool = False) -> dict:
    value = {
        "id": simulation.id,
        "primary_person_id": simulation.primary_person_id,
        "participant_ids": json.loads(simulation.participant_ids_json),
        "title": simulation.title,
        "goal": simulation.goal,
        "status": simulation.status,
        "round_count": simulation.round_count,
    }
    if include_rounds:
        value["rounds"] = [
            json.loads(item.state_json)
            for item in sorted(simulation.rounds, key=lambda row: row.round_number)
        ]
    return value


def _stance(evidence: list[dict], round_number: int, previous: str | None) -> str:
    negative = sum(
        item.get("emotion") in {"stress", "negative", "angry"} for item in evidence
    )
    positive = sum(
        item.get("emotion") in {"positive", "happy", "supportive"} for item in evidence
    )
    if previous and round_number > 1 and abs(positive - negative) <= 1:
        return previous
    if positive > negative:
        return "supportive"
    if negative > positive:
        return "concerned"
    return "undecided"


def _consensus(states: list[dict]) -> str:
    values = [item["stance"] for item in states]
    if values and len(set(values)) == 1:
        return values[0]
    return "mixed"
