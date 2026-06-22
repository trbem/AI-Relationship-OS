from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.graph.relationship_graph import RelationshipGraphService
from app.models import User
from app.schemas import RelationshipGraphResponse

router = APIRouter()


@router.get("/relationship-map", response_model=RelationshipGraphResponse)
def get_relationship_map(
    days: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipGraphResponse:
    payload = RelationshipGraphService().build_snapshot(db, current_user.id, days=days)
    return RelationshipGraphResponse(**payload)


@router.get("/relationship-timeline")
def get_relationship_timeline(
    checkpoints: str = "7,30,90",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    checkpoint_list = [int(x.strip()) for x in checkpoints.split(",") if x.strip().isdigit()]
    if not checkpoint_list:
        checkpoint_list = [7, 30, 90]
    return RelationshipGraphService().build_timeline(db, current_user.id, checkpoint_list)


@router.get("/knowledge-map")
def get_knowledge_map(
    days: int | None = 30,
    person_id: str | None = None,
    event_types: str | None = None,
    min_confidence: float = 0.5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    selected_types = (
        {value.strip() for value in event_types.split(",") if value.strip()}
        if event_types
        else None
    )
    return RelationshipGraphService().build_knowledge_map(
        db,
        current_user.id,
        days=days,
        person_id=person_id,
        event_types=selected_types,
        min_confidence=max(0.0, min(1.0, min_confidence)),
    )
