import json
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.catalog import PERSONA_CATALOG, select_template
from app.db import SessionLocal, get_db
from app.models import (
    PersonaWorld,
    User,
    WorldEvent,
    WorldImportTask,
    WorldPersona,
    WorldRelationship,
    WorldSimulation,
    WorldSimulationRound,
    WorldSource,
)
from app.services.free_web_search_service import FreeWebWorldSearchService
from app.services.world_ai_service import WorldAIService
from app.services.openai_web_search_service import (
    WORLD_IMPORT_ERROR_MESSAGES,
    OpenAIWebSearchService,
    WorldImportError,
)

router = APIRouter()
WORLD_CAPACITY = 50
ROLE_DISCLAIMER = "本结果是基于人物设定的角色沙盘，不是对真实人物行为的预测。"


class WorldRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    theme: str | None = Field(default=None, max_length=255)
    world_type: str = Field(default="custom", max_length=32)
    description: str | None = None
    world_background: str | None = None


class WorldPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    theme: str | None = None
    description: str | None = None
    world_background: str | None = None


class PersonaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    aliases: list[str] = []
    traits: list[str] = []
    motivations: list[str] = []
    values: list[str] = []
    abilities: list[str] = []
    communication: list[str] = []
    faction: str | None = None
    background: str | None = None
    avatar_url: str | None = None


class PersonaPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    aliases: list[str] | None = None
    traits: list[str] | None = None
    motivations: list[str] | None = None
    values: list[str] | None = None
    abilities: list[str] | None = None
    communication: list[str] | None = None
    faction: str | None = None
    background: str | None = None
    avatar_url: str | None = None


class RelationshipRequest(BaseModel):
    source_persona_id: str
    target_persona_id: str
    relationship_type: str = Field(min_length=1, max_length=64)
    directed: bool = True
    strength: float = Field(default=0.5, ge=0, le=1)
    description: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class RelationshipPatch(BaseModel):
    relationship_type: str | None = Field(default=None, min_length=1, max_length=64)
    directed: bool | None = None
    strength: float | None = Field(default=None, ge=0, le=1)
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class CatalogImportRequest(BaseModel):
    template_id: str
    limit: int = Field(default=20, ge=1, le=50)
    factions: list[str] = []
    core_persona_keys: list[str] = []


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    limit: int = Field(default=50, ge=1, le=50)
    provider: str = Field(default="free_web", pattern="^(free_web|openai_web_search)$")


class ConfirmImportRequest(BaseModel):
    world_id: str | None = None
    destination: str = Field(default="append", pattern="^(create|append)$")
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    relationship_indexes: list[int] = []


class DiscardImportRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SimulationRequest(BaseModel):
    title: str = Field(default="瑙掕壊娌欑洏", min_length=1, max_length=255)
    scenario: str = Field(min_length=1, max_length=5000)
    participant_ids: list[str] = Field(min_length=1, max_length=8)
    rounds: int = Field(default=3, ge=1, le=5)


class PromoteEventRequest(BaseModel):
    round_number: int = Field(ge=1, le=5)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    event_type: str = Field(default="derived", max_length=64)


def _world(db: Session, world_id: str, user_id: str) -> PersonaWorld:
    value = db.get(PersonaWorld, world_id)
    if not value or value.user_id != user_id:
        raise HTTPException(status_code=404, detail="角色世界不存在")
    return value


def _persona(db: Session, world: PersonaWorld, persona_id: str) -> WorldPersona:
    value = db.get(WorldPersona, persona_id)
    if not value or value.world_id != world.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    return value


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _completeness(persona: WorldPersona, relation_count: int = 0, has_source: bool = False) -> float:
    values = [
        bool(persona.name),
        bool(persona.summary),
        bool(_json(persona.traits_json, [])),
        bool(_json(persona.motivations_json, [])),
        bool(_json(persona.values_json, [])),
        bool(_json(persona.communication_json, [])),
        bool(persona.faction),
        bool(persona.background),
        relation_count > 0,
        has_source,
    ]
    return round(sum(values) / len(values), 3)


def _persona_dict(item: WorldPersona) -> dict:
    return {
        "id": item.id,
        "world_id": item.world_id,
        "name": item.name,
        "aliases": _json(item.aliases_json, []),
        "summary": item.summary,
        "traits": _json(item.traits_json, []),
        "motivations": _json(item.motivations_json, []),
        "values": _json(item.values_json, []),
        "abilities": _json(item.abilities_json, []),
        "communication": _json(item.communication_json, []),
        "faction": item.faction,
        "background": item.background,
        "avatar_url": item.avatar_url,
        "source_type": item.source_type,
        "source_ref": item.source_ref,
        "setting_completeness": item.setting_completeness,
    }


def _relationship_dict(item: WorldRelationship) -> dict:
    return {
        "id": item.id,
        "source_persona_id": item.source_persona_id,
        "target_persona_id": item.target_persona_id,
        "relationship_type": item.relationship_type,
        "directed": item.directed,
        "strength": item.strength,
        "description": item.description,
        "confidence": item.confidence,
        "source_type": item.source_type,
        "source_ref": item.source_ref,
    }


def _world_dict(item: PersonaWorld, details: bool = False) -> dict:
    result = {
        "id": item.id,
        "name": item.name,
        "theme": item.theme,
        "world_type": item.world_type,
        "source_type": item.source_type,
        "version": item.version,
        "description": item.description,
        "world_background": item.world_background,
        "persona_count": len(item.personas),
        "relationship_count": len(item.relationships),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
    if details:
        result["personas"] = [_persona_dict(value) for value in item.personas]
        result["relationships"] = [_relationship_dict(value) for value in item.relationships]
        result["sources"] = [
            {
                "id": source.id,
                "persona_id": source.persona_id,
                "relationship_id": source.relationship_id,
                "source_type": source.source_type,
                "external_id": source.external_id,
                "url": source.url,
                "title": source.title,
            }
            for source in item.sources
        ]
    return result


@router.post("/worlds", status_code=201)
def create_world(
    request: WorldRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    value = PersonaWorld(user_id=current_user.id, source_type="manual", **request.model_dump())
    db.add(value)
    db.commit()
    db.refresh(value)
    return _world_dict(value)


@router.get("/worlds")
def list_worlds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.query(PersonaWorld).filter(PersonaWorld.user_id == current_user.id).all()
    return [_world_dict(row) for row in rows]


@router.get("/worlds/{world_id}")
def get_world(
    world_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return _world_dict(_world(db, world_id, current_user.id), details=True)


@router.patch("/worlds/{world_id}")
def update_world(
    world_id: str,
    request: WorldPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    value = _world(db, world_id, current_user.id)
    for key, field in request.model_dump(exclude_unset=True).items():
        setattr(value, key, field)
    db.commit()
    return _world_dict(value, details=True)


@router.delete("/worlds/{world_id}", status_code=204)
def delete_world(
    world_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    db.delete(_world(db, world_id, current_user.id))
    db.commit()


@router.post("/worlds/{world_id}/personas", status_code=201)
def create_persona(
    world_id: str,
    request: PersonaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    if len(world.personas) >= WORLD_CAPACITY:
        raise HTTPException(status_code=400, detail=f"每个角色世界最多 {WORLD_CAPACITY} 人")
    data = request.model_dump()
    item = WorldPersona(
        world_id=world.id,
        name=data["name"],
        summary=data["summary"],
        aliases_json=json.dumps(data["aliases"], ensure_ascii=False),
        traits_json=json.dumps(data["traits"], ensure_ascii=False),
        motivations_json=json.dumps(data["motivations"], ensure_ascii=False),
        values_json=json.dumps(data["values"], ensure_ascii=False),
        abilities_json=json.dumps(data["abilities"], ensure_ascii=False),
        communication_json=json.dumps(data["communication"], ensure_ascii=False),
        faction=data["faction"],
        background=data["background"],
        avatar_url=data["avatar_url"],
        source_type="manual",
    )
    item.setting_completeness = _completeness(item)
    db.add(item)
    db.commit()
    return _persona_dict(item)


@router.patch("/worlds/{world_id}/personas/{persona_id}")
def update_persona(
    world_id: str,
    persona_id: str,
    request: PersonaPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    item = _persona(db, world, persona_id)
    data = request.model_dump(exclude_unset=True)
    list_fields = {
        "aliases": "aliases_json",
        "traits": "traits_json",
        "motivations": "motivations_json",
        "values": "values_json",
        "abilities": "abilities_json",
        "communication": "communication_json",
    }
    for key, value in data.items():
        if key in list_fields:
            setattr(item, list_fields[key], json.dumps(value, ensure_ascii=False))
        else:
            setattr(item, key, value)
    relation_count = sum(
        rel.source_persona_id == item.id or rel.target_persona_id == item.id
        for rel in world.relationships
    )
    item.setting_completeness = _completeness(
        item, relation_count, any(source.persona_id == item.id for source in world.sources)
    )
    db.commit()
    return _persona_dict(item)


@router.delete("/worlds/{world_id}/personas/{persona_id}", status_code=204)
def delete_persona(
    world_id: str,
    persona_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    world = _world(db, world_id, current_user.id)
    item = _persona(db, world, persona_id)
    relationship_ids = [
        rel.id for rel in world.relationships
        if rel.source_persona_id == item.id or rel.target_persona_id == item.id
    ]
    db.query(WorldSource).filter(
        or_(
            WorldSource.persona_id == item.id,
            WorldSource.relationship_id.in_(relationship_ids),
        )
    ).delete(synchronize_session=False)
    db.query(WorldRelationship).filter(
        or_(
            WorldRelationship.source_persona_id == item.id,
            WorldRelationship.target_persona_id == item.id,
        )
    ).delete(synchronize_session=False)
    db.delete(item)
    db.commit()


@router.post("/worlds/{world_id}/relationships", status_code=201)
def create_relationship(
    world_id: str,
    request: RelationshipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    if request.source_persona_id == request.target_persona_id:
        raise HTTPException(status_code=400, detail="关系两端不能是同一人物")
    source = _persona(db, world, request.source_persona_id)
    target = _persona(db, world, request.target_persona_id)
    item = WorldRelationship(
        world_id=world.id,
        source_persona_id=source.id,
        target_persona_id=target.id,
        source_type="manual",
        **request.model_dump(exclude={"source_persona_id", "target_persona_id"}),
    )
    db.add(item)
    db.flush()
    for persona in (source, target):
        relation_count = db.query(WorldRelationship).filter(
            WorldRelationship.world_id == world.id,
            or_(
                WorldRelationship.source_persona_id == persona.id,
                WorldRelationship.target_persona_id == persona.id,
            ),
        ).count()
        persona.setting_completeness = _completeness(
            persona,
            relation_count,
            db.query(WorldSource).filter(WorldSource.persona_id == persona.id).first()
            is not None,
        )
    db.commit()
    return _relationship_dict(item)


@router.patch("/worlds/{world_id}/relationships/{relationship_id}")
def update_relationship(
    world_id: str,
    relationship_id: str,
    request: RelationshipPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    item = db.get(WorldRelationship, relationship_id)
    if not item or item.world_id != world.id:
        raise HTTPException(status_code=404, detail="关系不存在")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    return _relationship_dict(item)


@router.delete("/worlds/{world_id}/relationships/{relationship_id}", status_code=204)
def delete_relationship(
    world_id: str,
    relationship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    world = _world(db, world_id, current_user.id)
    item = db.get(WorldRelationship, relationship_id)
    if not item or item.world_id != world.id:
        raise HTTPException(status_code=404, detail="关系不存在")
    db.query(WorldSource).filter(WorldSource.relationship_id == item.id).delete()
    db.delete(item)
    db.commit()


@router.get("/persona-catalog")
def persona_catalog() -> list[dict]:
    return [
        {
            "id": value["id"],
            "name": value["name"],
            "theme": value["theme"],
            "world_type": value["world_type"],
            "version": value["version"],
            "description": value["description"],
            "source": value["source"],
            "persona_count": len(value["personas"]),
            "relationship_count": len(value["relationships"]),
            "factions": sorted({item["faction"] for item in value["personas"]}),
            "personas": [{"key": item["key"], "name": item["name"]} for item in value["personas"]],
        }
        for value in PERSONA_CATALOG.values()
    ]


@router.post("/worlds/{world_id}/import/catalog")
def import_catalog(
    world_id: str,
    request: CatalogImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    template = PERSONA_CATALOG.get(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    remaining = WORLD_CAPACITY - len(world.personas)
    if remaining <= 0:
        raise HTTPException(status_code=400, detail=f"角色世界已达到 {WORLD_CAPACITY} 人上限")
    was_empty = not world.personas
    personas, relationships = select_template(
        template,
        min(request.limit, remaining),
        request.factions or None,
        request.core_persona_keys or None,
    )
    existing_refs = {item.source_ref for item in world.personas if item.source_ref}
    key_to_id = {
        item.source_ref.split(":", 1)[1]: item.id
        for item in world.personas
        if item.source_ref and item.source_ref.startswith(f"{template['id']}:")
    }
    imported = 0
    for data in personas:
        source_ref = f"{template['id']}:{data['key']}"
        if source_ref in existing_refs:
            continue
        item = WorldPersona(
            world_id=world.id,
            name=data["name"],
            aliases_json=json.dumps(data["aliases"], ensure_ascii=False),
            summary=data["summary"],
            traits_json=json.dumps(data["traits"], ensure_ascii=False),
            motivations_json=json.dumps(data["motivations"], ensure_ascii=False),
            values_json=json.dumps(data["values"], ensure_ascii=False),
            abilities_json=json.dumps(data["abilities"], ensure_ascii=False),
            communication_json=json.dumps(data["communication"], ensure_ascii=False),
            faction=data["faction"],
            background=data["background"],
            source_type="curated",
            source_ref=source_ref,
            setting_completeness=0.8,
        )
        db.add(item)
        db.flush()
        key_to_id[data["key"]] = item.id
        imported += 1
    for rel in relationships:
        source_id = key_to_id.get(rel["source"])
        target_id = key_to_id.get(rel["target"])
        if not source_id or not target_id:
            continue
        exists = db.query(WorldRelationship).filter_by(
            world_id=world.id,
            source_persona_id=source_id,
            target_persona_id=target_id,
            relationship_type=rel["type"],
        ).first()
        if not exists:
            db.add(
                WorldRelationship(
                    world_id=world.id,
                    source_persona_id=source_id,
                    target_persona_id=target_id,
                    relationship_type=rel["type"],
                    directed=rel["directed"],
                    strength=rel["strength"],
                    description=rel["description"],
                    confidence=rel["confidence"],
                    source_type="curated",
                    source_ref=template["id"],
                )
            )
    if was_empty:
        world.source_type = "curated"
    world.version = template["version"]
    db.commit()
    return {"imported_personas": imported, "world": _world_dict(world, details=True)}


class ResolveImportRequest(BaseModel):
    selected_option_id: str = Field(min_length=1, max_length=255)


class GenerateFallbackRequest(BaseModel):
    mode: str = Field(default="generate_missing", pattern="^(generate_missing|fill_to_limit)$")
    target_count: int | None = Field(default=None, ge=1, le=50)


@router.post("/world-imports/search", status_code=202)
def search_world_import(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = WorldImportTask(
        user_id=current_user.id,
        query=request.query,
        requested_limit=min(request.limit, WORLD_CAPACITY),
        status="queued",
        stage="queued",
        progress=0.0,
        result_json=json.dumps(
            {
                "query": request.query,
                "provider": request.provider,
                "candidates": [],
                "relationships": [],
                "errors": [],
                "source_failures": [],
            },
            ensure_ascii=False,
        ),
    )
    db.add(task)
    db.commit()
    _start_world_import_task(task.id)
    return _task_dict(task)


@router.get("/world-imports/{task_id}")
def get_world_import(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    return _task_dict(task)


def _task_dict(task: WorldImportTask) -> dict:
    result = _json(task.result_json, {})
    error = _json(task.error, None) if task.error else None
    return {
        "id": task.id,
        "task_id": task.id,
        "world_id": task.world_id,
        "query": task.query,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "requested_limit": task.requested_limit,
        "result": result,
        "error": error,
        "can_retry": task.status in {"failed", "partial"},
    }


def _start_world_import_task(task_id: str) -> None:
    thread = threading.Thread(
        target=_run_world_import_task,
        args=(task_id,),
        name=f"world-import-{task_id[:8]}",
        daemon=True,
    )
    thread.start()


def _run_world_import_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(WorldImportTask, task_id)
        if not task or task.status in {"discarded", "completed"}:
            return
        task.status = "searching"
        task.stage = "searching"
        task.progress = 0.15
        db.commit()
        result = _search_world_with_provider(task)
        task.result_json = json.dumps(result, ensure_ascii=False)
        if result.get("status_hint") == "needs_disambiguation":
            task.status = "needs_disambiguation"
            task.stage = "needs_disambiguation"
            task.progress = 0.45
        else:
            task.status = "partial" if result.get("partial") else "preview"
            task.stage = "preview"
            task.progress = 1.0
        task.error = None
    except WorldImportError as exc:
        task = db.get(WorldImportTask, task_id)
        if task:
            _fail_task(task, exc.detail.to_dict())
    except Exception as exc:  # pragma: no cover - background safety net.
        task = db.get(WorldImportTask, task_id)
        if task:
            _fail_task(
                task,
                _error_detail(
                    "INVALID_PROVIDER_RESPONSE",
                    stage="extracting",
                    retryable=True,
                    technical_summary=exc.__class__.__name__,
                ),
            )
    finally:
        db.commit()
        db.close()


def _fail_task(task: WorldImportTask, error: dict) -> None:
    result = _json(task.result_json, {})
    result.setdefault("errors", []).append(error)
    task.result_json = json.dumps(result, ensure_ascii=False)
    task.status = "failed"
    task.stage = error.get("stage") or task.stage
    task.progress = 1.0
    task.error = json.dumps(error, ensure_ascii=False)


def _search_world_with_provider(task: WorldImportTask) -> dict:
    result = _json(task.result_json, {})
    provider = result.get("provider") or "free_web"
    if provider == "openai_web_search":
        data = OpenAIWebSearchService().search_world(task.query, task.requested_limit)
    else:
        data = FreeWebWorldSearchService().search_world(task.query, task.requested_limit)
        provider = "free_web"
    data["provider"] = provider
    return data


def _error_detail(
    code: str,
    *,
    stage: str,
    retryable: bool,
    technical_summary: str = "",
) -> dict:
    return {
        "code": code,
        "message": WORLD_IMPORT_ERROR_MESSAGES.get(code, code),
        "retryable": retryable,
        "stage": stage,
        "technical_summary": technical_summary[:500],
    }


def _import_task(db: Session, task_id: str, user_id: str) -> WorldImportTask:
    task = db.get(WorldImportTask, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return task


@router.post("/world-imports/{task_id}/retry", status_code=202)
def retry_world_import(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    if task.status not in {"failed", "partial"}:
        raise HTTPException(status_code=409, detail="当前任务状态不能重试")
    task.status = "queued"
    task.stage = "queued"
    task.progress = 0.0
    task.error = None
    db.commit()
    _start_world_import_task(task.id)
    return _task_dict(task)


@router.post("/world-imports/{task_id}/cancel")
def cancel_world_import(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    if task.status in {"completed", "discarded"}:
        return _task_dict(task)
    task.status = "discarded"
    task.stage = "discarded"
    task.error = json.dumps(
        _error_detail(
            "SEARCH_TIMEOUT",
            stage="discarded",
            retryable=True,
            technical_summary="cancelled by user",
        ),
        ensure_ascii=False,
    )
    db.commit()
    return _task_dict(task)


@router.post("/world-imports/{task_id}/resolve", status_code=202)
def resolve_world_import(
    task_id: str,
    request: ResolveImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    if task.status != "needs_disambiguation":
        return _task_dict(task)
    result = _json(task.result_json, {})
    options = result.get("disambiguation_options", [])
    selected = next(
        (item for item in options if str(item.get("id")) == request.selected_option_id),
        None,
    )
    if selected is None:
        raise HTTPException(status_code=404, detail="未找到该作品候选")
    task.query = selected.get("title") or task.query
    task.status = "queued"
    task.stage = "queued"
    task.progress = 0.0
    task.error = None
    db.commit()
    _start_world_import_task(task.id)
    return _task_dict(task)


@router.post("/world-imports/{task_id}/generate-fallback")
def generate_world_import_fallback(
    task_id: str,
    request: GenerateFallbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    result = _json(task.result_json, {})
    current = len(result.get("candidates", []))
    target = max(1, min(WORLD_CAPACITY, request.target_count or task.requested_limit))
    limit = max(1, target - current) if request.mode == "generate_missing" else target
    generated = WorldAIService().generated_import_preview(
        task.query,
        limit,
        source_failures=result.get("source_failures", []),
    )
    existing_ids = {item.get("id") for item in result.get("candidates", [])}
    additions = [
        item for item in generated.get("candidates", [])
        if item.get("id") not in existing_ids
    ]
    result.setdefault("candidates", []).extend(additions[: max(0, target - current)])
    result.setdefault("relationships", []).extend(generated.get("relationships", []))
    result["fallback_mode"] = "model_generated"
    result["generated_notice"] = generated.get("generated_notice")
    result["partial"] = True
    task.result_json = json.dumps(result, ensure_ascii=False)
    task.status = "partial" if result.get("candidates") else "failed"
    task.stage = "preview" if result.get("candidates") else "failed"
    task.progress = 1.0
    task.error = None
    db.commit()
    return _task_dict(task)


@router.post("/world-imports/{task_id}/confirm")
def confirm_world_import(
    task_id: str,
    request: ConfirmImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = _import_task(db, task_id, current_user.id)
    result = _json(task.result_json, {})
    if task.status not in {"preview", "partial"}:
        raise HTTPException(status_code=409, detail="任务尚未进入可确认状态")
    world = _resolve_import_destination(db, request, result, current_user.id)
    selected = [
        item for item in result.get("candidates", []) if item.get("id") in request.candidate_ids
    ]
    selected = [item for item in selected if _candidate_is_importable(item)]
    if not selected:
        raise HTTPException(status_code=400, detail="没有可导入的人物；联网候选需要真实 URL，生成候选需要显式触发")
    if len(world.personas) + len(selected) > WORLD_CAPACITY:
        raise HTTPException(status_code=400, detail=f"确认后人物数量将超过 {WORLD_CAPACITY}")
    imported = 0
    external_to_persona: dict[str, WorldPersona] = {}
    for data in selected:
        existing = db.query(WorldPersona).filter(
            WorldPersona.world_id == world.id,
            or_(
                WorldPersona.source_ref == data["id"],
                WorldPersona.name == data["name"],
            ),
        ).first()
        if existing:
            external_to_persona[data["id"]] = existing
            continue
        item = WorldPersona(
            world_id=world.id,
            name=data["name"],
            aliases_json=json.dumps(data.get("aliases", []), ensure_ascii=False),
            summary=data.get("summary") or data.get("description") or "来源未提供摘要。",
            traits_json=json.dumps(data.get("traits", []), ensure_ascii=False),
            motivations_json=json.dumps(data.get("motivations", []), ensure_ascii=False),
            communication_json=json.dumps(data.get("communication", []), ensure_ascii=False),
            values_json=json.dumps(data.get("values", []), ensure_ascii=False),
            abilities_json=json.dumps(data.get("abilities", []), ensure_ascii=False),
            faction=data.get("faction"),
            source_type=data.get("source_type", "openai_web_search"),
            background=data.get("background"),
            source_ref=data["id"],
            setting_completeness=0.55 if data.get("verification_status") == "web_verified" else 0.35,
        )
        db.add(item)
        db.flush()
        external_to_persona[data["id"]] = item
        imported += 1
        for source in data.get("sources", []):
            if not _valid_source_url(source.get("url")):
                continue
            db.add(
                WorldSource(
                    world_id=world.id,
                    persona_id=item.id,
                    source_type=source.get("source_type") or data.get("source_type", "openai_web_search"),
                    external_id=source.get("external_id"),
                    url=source["url"],
                    title=source.get("title"),
                )
            )
    relationships = result.get("relationships", [])
    relationship_indexes = request.relationship_indexes or list(range(len(relationships)))
    imported_relationships = 0
    for index in relationship_indexes:
        if index < 0 or index >= len(relationships):
            continue
        rel = relationships[index]
        source = external_to_persona.get(rel.get("source"))
        target = external_to_persona.get(rel.get("target"))
        if source and target:
            existing_rel = db.query(WorldRelationship).filter(
                WorldRelationship.world_id == world.id,
                WorldRelationship.source_persona_id == source.id,
                WorldRelationship.target_persona_id == target.id,
                WorldRelationship.relationship_type == rel["type"],
            ).first()
            if existing_rel:
                continue
            db.add(
                WorldRelationship(
                    world_id=world.id,
                    source_persona_id=source.id,
                    target_persona_id=target.id,
                    relationship_type=rel["type"],
                    directed=rel.get("directed", True),
                    strength=rel.get("strength", 0.5),
                    description=rel.get("description"),
                    confidence=rel.get("confidence", 0.7),
                    source_type=rel.get("source_type", "wikidata"),
                    source_ref=rel.get("source_ref"),
                )
            )
            imported_relationships += 1
    task.world_id = world.id
    task.status = "completed"
    task.stage = "completed"
    db.commit()
    return {
        "imported_personas": imported,
        "imported_relationships": imported_relationships,
        "world": _world_dict(world, details=True),
    }


def _candidate_is_importable(item: dict) -> bool:
    if item.get("verification_status") == "generated_unverified":
        return item.get("source_type") == "generated_unverified"
    return any(_valid_source_url(source.get("url")) for source in item.get("sources", []))


def _valid_source_url(value: object) -> bool:
    text = str(value or "")
    return text.startswith(("http://", "https://"))


def _resolve_import_destination(
    db: Session,
    request: ConfirmImportRequest,
    result: dict,
    user_id: str,
) -> PersonaWorld:
    if request.destination == "append" or request.world_id:
        if not request.world_id:
            raise HTTPException(status_code=400, detail="追加导入需要 world_id")
        return _world(db, request.world_id, user_id)
    work = result.get("work") if isinstance(result.get("work"), dict) else {}
    name = str(work.get("title") or result.get("query") or "AI 导入角色世界").strip()
    world = PersonaWorld(
        user_id=user_id,
        name=name[:255],
        theme=str(work.get("medium") or "AI 联网导入")[:255],
        world_type="fictional",
        source_type="openai_web_search",
        version=str(work.get("version") or "")[:64] or None,
        description=work.get("summary") or None,
    )
    db.add(world)
    db.flush()
    return world


@router.post("/world-imports/{task_id}/discard")
def discard_world_import(
    task_id: str,
    request: DiscardImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = db.get(WorldImportTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    task.status = "discarded"
    task.stage = "discarded"
    if request.reason:
        task.error = request.reason
    db.commit()
    return _task_dict(task)


@router.get("/worlds/{world_id}/graph")
def world_graph(
    world_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    degrees = {item.id: 0 for item in world.personas}
    for rel in world.relationships:
        degrees[rel.source_persona_id] = degrees.get(rel.source_persona_id, 0) + 1
        degrees[rel.target_persona_id] = degrees.get(rel.target_persona_id, 0) + 1
    return {
        "nodes": [
            {
                "id": item.id,
                "name": item.name,
                "type": "persona",
                "group": item.faction or "未分组",
                "relationship_score": item.setting_completeness * 100,
                "weight": 1 + degrees.get(item.id, 0) * 0.2,
                "emotion": "setting",
                "summary": item.summary,
                "hint": f"设定完整度 {round(item.setting_completeness * 100)}%",
                "score_components": {"setting_completeness": item.setting_completeness},
                "change_reasons": [f"来源：{item.source_type}"],
                "metadata": {
                    "summary": item.summary,
                    "source_type": item.source_type,
                    "setting_completeness": item.setting_completeness,
                },
            }
            for item in world.personas
        ],
        "links": [
            {
                "id": item.id,
                "source": item.source_persona_id,
                "target": item.target_persona_id,
                "relation_type": item.relationship_type,
                "strength": item.strength,
                "width": 1 + item.strength * 4,
                "interaction": 0,
                "emotion": "setting",
                "directed": item.directed,
                "metadata": {
                    "description": item.description,
                    "confidence": item.confidence,
                    "source_type": item.source_type,
                },
            }
            for item in world.relationships
        ],
        "insights": {
            "world_id": world.id,
            "mode": "role_sandbox",
            "disclaimer": ROLE_DISCLAIMER,
        },
    }


@router.post("/worlds/{world_id}/simulations", status_code=201)
def run_world_simulation(
    world_id: str,
    request: SimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    participant_ids = list(dict.fromkeys(request.participant_ids))
    if len(participant_ids) > 8:
        raise HTTPException(status_code=400, detail="每次角色推演最多 8 人")
    people = db.query(WorldPersona).filter(
        WorldPersona.world_id == world.id,
        WorldPersona.id.in_(participant_ids),
    ).all()
    if len(people) != len(participant_ids):
        raise HTTPException(status_code=404, detail="一个或多个人物不存在")
    relations = [
        rel for rel in world.relationships
        if rel.source_persona_id in participant_ids and rel.target_persona_id in participant_ids
    ]
    completeness = round(sum(item.setting_completeness for item in people) / len(people), 3)
    sourced = sum(item.source_type in {"curated", "wikidata", "wikipedia"} for item in people)
    source_coverage = round(sourced / len(people), 3)
    payload = WorldAIService().run_simulation(
        world=world,
        people=people,
        relationships=relations,
        scenario=request.scenario,
        rounds=request.rounds,
        completeness=completeness,
        source_coverage=source_coverage,
        disclaimer=ROLE_DISCLAIMER,
    )
    simulation = WorldSimulation(
        world_id=world.id,
        user_id=current_user.id,
        title=request.title,
        scenario=request.scenario,
        participant_ids_json=json.dumps(participant_ids),
        round_count=request.rounds,
        setting_completeness=completeness,
        source_coverage=source_coverage,
    )
    db.add(simulation)
    db.flush()
    for state in payload["rounds"]:
        db.add(
            WorldSimulationRound(
                simulation_id=simulation.id,
                round_number=state["round"],
                state_json=json.dumps(state, ensure_ascii=False),
            )
        )
    db.commit()
    return _simulation_dict(simulation)


def _simulation_dict(item: WorldSimulation) -> dict:
    rounds = [
        _json(row.state_json, {})
        for row in sorted(item.rounds, key=lambda value: value.round_number)
    ]
    return {
        "id": item.id,
        "world_id": item.world_id,
        "title": item.title,
        "scenario": item.scenario,
        "participant_ids": _json(item.participant_ids_json, []),
        "round_count": item.round_count,
        "status": item.status,
        "mode": "role_sandbox",
        "setting_completeness": item.setting_completeness,
        "source_coverage": item.source_coverage,
        "language": rounds[0].get("language") if rounds else None,
        "fallback": any(round_data.get("fallback") for round_data in rounds),
        "disclaimer": ROLE_DISCLAIMER,
        "rounds": rounds,
    }


@router.get("/worlds/{world_id}/simulations")
def list_world_simulations(
    world_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    world = _world(db, world_id, current_user.id)
    rows = (
        db.query(WorldSimulation)
        .filter(WorldSimulation.world_id == world.id)
        .order_by(WorldSimulation.created_at.desc())
        .all()
    )
    return [_simulation_dict(item) for item in rows]


@router.get("/worlds/{world_id}/simulations/{simulation_id}")
def get_world_simulation(
    world_id: str,
    simulation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    item = db.get(WorldSimulation, simulation_id)
    if not item or item.world_id != world.id:
        raise HTTPException(status_code=404, detail="角色沙盘不存在")
    return _simulation_dict(item)


@router.get("/worlds/{world_id}/simulations/{simulation_id}/rounds/{round_number}")
def get_world_simulation_round(
    world_id: str,
    simulation_id: str,
    round_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    item = db.get(WorldSimulation, simulation_id)
    if not item or item.world_id != world.id:
        raise HTTPException(status_code=404, detail="角色沙盘不存在")
    row = next((value for value in item.rounds if value.round_number == round_number), None)
    if row is None:
        raise HTTPException(status_code=404, detail="轮次不存在")
    return _json(row.state_json, {})


@router.post("/worlds/{world_id}/simulations/{simulation_id}/promote", status_code=201)
def promote_world_event(
    world_id: str,
    simulation_id: str,
    request: PromoteEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    simulation = db.get(WorldSimulation, simulation_id)
    if not simulation or simulation.world_id != world.id:
        raise HTTPException(status_code=404, detail="角色沙盘不存在")
    if request.round_number > simulation.round_count:
        raise HTTPException(status_code=400, detail="轮次不存在")
    event = WorldEvent(
        world_id=world.id,
        title=request.title,
        summary=request.summary,
        event_type=request.event_type,
        is_simulated=True,
        source_simulation_id=simulation.id,
        source_round_number=request.round_number,
    )
    db.add(event)
    db.commit()
    return {
        "id": event.id,
        "title": event.title,
        "summary": event.summary,
        "event_type": event.event_type,
        "is_simulated": True,
        "label": "\u865a\u6784\u884d\u751f\u5185\u5bb9",
    }


@router.get("/worlds/{world_id}/export")
def export_world(
    world_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    world = _world(db, world_id, current_user.id)
    return {
        "format": "relationship-os-persona-world",
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "world": _world_dict(world, details=True),
    }


@router.post("/worlds/import", status_code=201)
def import_world(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if payload.get("format") != "relationship-os-persona-world" or payload.get("version") != 1:
        raise HTTPException(status_code=400, detail="不支持的角色世界格式")
    data = payload.get("world")
    if not isinstance(data, dict) or not data.get("name"):
        raise HTTPException(status_code=400, detail="角色世界内容无效")
    personas = data.get("personas", [])
    if len(personas) > WORLD_CAPACITY:
        raise HTTPException(status_code=400, detail=f"角色世界人物超过 {WORLD_CAPACITY} 人")
    world = PersonaWorld(
        user_id=current_user.id,
        name=data["name"],
        theme=data.get("theme"),
        world_type=data.get("world_type", "custom"),
        source_type=data.get("source_type", "manual"),
        version=data.get("version"),
        description=data.get("description"),
        world_background=data.get("world_background"),
    )
    db.add(world)
    db.flush()
    id_map = {}
    for source in personas:
        item = WorldPersona(
            world_id=world.id,
            name=source["name"],
            summary=source.get("summary") or "未提供简介。",
            aliases_json=json.dumps(source.get("aliases", []), ensure_ascii=False),
            traits_json=json.dumps(source.get("traits", []), ensure_ascii=False),
            motivations_json=json.dumps(source.get("motivations", []), ensure_ascii=False),
            values_json=json.dumps(source.get("values", []), ensure_ascii=False),
            abilities_json=json.dumps(source.get("abilities", []), ensure_ascii=False),
            communication_json=json.dumps(source.get("communication", []), ensure_ascii=False),
            faction=source.get("faction"),
            background=source.get("background"),
            avatar_url=source.get("avatar_url"),
            source_type=source.get("source_type", "manual"),
            source_ref=source.get("source_ref"),
            setting_completeness=source.get("setting_completeness", 0),
        )
        db.add(item)
        db.flush()
        id_map[source.get("id")] = item.id
    relationship_id_map = {}
    for source in data.get("relationships", []):
        if source.get("source_persona_id") in id_map and source.get("target_persona_id") in id_map:
            relationship = WorldRelationship(
                world_id=world.id,
                source_persona_id=id_map[source["source_persona_id"]],
                target_persona_id=id_map[source["target_persona_id"]],
                relationship_type=source["relationship_type"],
                directed=source.get("directed", True),
                strength=source.get("strength", 0.5),
                description=source.get("description"),
                confidence=source.get("confidence", 0.5),
                source_type=source.get("source_type", "manual"),
                source_ref=source.get("source_ref"),
            )
            db.add(relationship)
            db.flush()
            relationship_id_map[source.get("id")] = relationship.id
    for source in data.get("sources", []):
        persona_id = id_map.get(source.get("persona_id"))
        relationship_id = relationship_id_map.get(source.get("relationship_id"))
        if not persona_id and not relationship_id:
            continue
        db.add(
            WorldSource(
                world_id=world.id,
                persona_id=persona_id,
                relationship_id=relationship_id,
                source_type=source["source_type"],
                external_id=source.get("external_id"),
                url=source["url"],
                title=source.get("title"),
            )
        )
    db.commit()
    return _world_dict(world, details=True)
