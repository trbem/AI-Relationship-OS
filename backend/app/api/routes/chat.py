import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_data_dir
from app.db import get_db
from app.models import ImportTask, Message, User
from app.schemas import (
    ChatPreviewMessage,
    ChatPreviewResponse,
    ImportChatResponse,
    ImportTaskResponse,
    MessageResponse,
)
from app.services.chat_parser import ChatParserService
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.import_service import ImportTaskProcessor
from app.services.relationship_event_service import RelationshipEventService

router = APIRouter()


def _resolve_contact_name(
    sender_names: list[str],
    user_email: str,
    self_name: str | None = None,
) -> str:
    normalized_self_name = self_name.strip().casefold() if self_name else None
    self_aliases = {
        "me",
        "myself",
        "我",
        user_email.casefold(),
        user_email.split("@", 1)[0].casefold(),
    }
    if normalized_self_name:
        self_aliases.add(normalized_self_name)

    normalized_senders = {name.strip().casefold() for name in sender_names}
    if normalized_self_name and normalized_self_name not in normalized_senders:
        raise HTTPException(
            status_code=400,
            detail="指定的本人名称未在聊天文件中找到 (was not found)",
        )

    contact_names = [
        name
        for name in dict.fromkeys(sender_names)
        if name.strip().casefold() not in self_aliases
    ]
    if len(contact_names) != 1:
        raise HTTPException(
            status_code=400,
            detail="当前仅支持一对一聊天，请明确填写本人名称",
        )
    return contact_names[0]


def _task_response(task: ImportTask) -> ImportTaskResponse:
    return ImportTaskResponse(
        task_id=task.id,
        status=task.status,
        stage=task.stage,
        progress=task.progress,
        filename=task.filename,
        file_hash=task.file_hash,
        encoding=task.encoding,
        contact_name=task.contact_name,
        person_id=task.person_id,
        parsed_count=task.parsed_count,
        imported_count=task.imported_count,
        duplicate_count=task.duplicate_count,
        attempts=task.attempts,
        error=task.error,
    )


def _parse_preview(filename: str, raw_bytes: bytes) -> tuple[ChatPreviewResponse, str, str]:
    extracted = DocumentTextExtractor().extract(filename, raw_bytes)
    parser = ChatParserService()
    fmt = extracted.format if extracted.format in parser.supported_formats else parser.detect_format(filename)
    parsed = parser.parse(extracted.text, fmt)
    if not parsed:
        raise HTTPException(status_code=400, detail="未找到有效聊天消息")
    sender_names = list(dict.fromkeys(item.sender_name for item in parsed))
    return (
        ChatPreviewResponse(
            filename=filename,
            format=fmt,
            encoding=extracted.encoding or extracted.extraction_method,
            input_type=extracted.input_type,
            extraction_method=extracted.extraction_method,
            recognized_text=extracted.text[:8000],
            import_candidates=sender_names,
            warnings=extracted.warnings,
            message_count=len(parsed),
            sender_names=sender_names,
            sample=[
                ChatPreviewMessage(
                    sender_name=item.sender_name,
                    content=item.content,
                    sent_at=item.sent_at.isoformat() if item.sent_at else None,
                )
                for item in parsed[:10]
            ],
        ),
        extracted.text,
        extracted.encoding or extracted.extraction_method,
    )


@router.post("/preview", response_model=ChatPreviewResponse)
async def preview_chat(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> ChatPreviewResponse:
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="聊天文件为空")
    if len(raw_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="聊天文件不能超过 50 MB")
    filename = Path(file.filename or "chat.txt").name
    try:
        preview, _, _ = _parse_preview(filename, raw_bytes)
        return preview
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import", response_model=ImportChatResponse, status_code=202)
async def import_chat(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    self_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportChatResponse:
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="聊天文件为空")
    if len(raw_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="聊天文件不能超过 50 MB")

    filename = Path(file.filename or "chat.txt").name
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    try:
        _, extracted_text, extracted_encoding = _parse_preview(filename, raw_bytes)
    except (ValueError, HTTPException) as exc:
        error_detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        task_id = str(uuid4())
        imports_dir = get_data_dir() / "imports"
        imports_dir.mkdir(parents=True, exist_ok=True)
        stored_path = imports_dir / f"{task_id}.upload"
        stored_path.write_bytes(raw_bytes)
        task = ImportTask(
            id=task_id,
            user_id=current_user.id,
            filename=filename,
            stored_path=str(stored_path),
            file_hash=file_hash,
            self_name=self_name.strip() if self_name else None,
            status="failed",
            stage="failed",
            progress=100,
            error=str(error_detail)[:2000],
            attempts=1,
        )
        db.add(task)
        db.commit()
        return ImportChatResponse(task_id=task.id, import_id=task.id)

    normalized_self_name = self_name.strip() if self_name else None
    previous = db.scalar(
        select(ImportTask)
        .where(
            ImportTask.user_id == current_user.id,
            ImportTask.file_hash == file_hash,
            ImportTask.self_name == normalized_self_name,
            ImportTask.status == "completed",
        )
        .order_by(ImportTask.created_at.desc())
    )
    task_id = str(uuid4())
    imports_dir = get_data_dir() / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    stored_path = imports_dir / f"{task_id}.upload"
    if previous:
        task = ImportTask(
            id=task_id,
            user_id=current_user.id,
            filename=filename,
            stored_path=previous.stored_path,
            file_hash=file_hash,
            self_name=normalized_self_name,
            encoding=previous.encoding,
            status="completed",
            stage="completed",
            progress=100,
            contact_name=previous.contact_name,
            person_id=previous.person_id,
            parsed_count=previous.parsed_count,
            imported_count=0,
            duplicate_count=previous.parsed_count,
        )
        db.add(task)
        db.commit()
        return ImportChatResponse(task_id=task.id, import_id=task.id)
    stored_path.write_bytes(extracted_text.encode("utf-8"))
    task = ImportTask(
        id=task_id,
        user_id=current_user.id,
        filename=filename,
        stored_path=str(stored_path),
        file_hash=file_hash,
        self_name=normalized_self_name,
        encoding=extracted_encoding,
    )
    db.add(task)
    db.commit()
    background_tasks.add_task(ImportTaskProcessor().run, task.id)
    return ImportChatResponse(task_id=task.id, import_id=task.id)


@router.get("/imports", response_model=list[ImportTaskResponse])
def list_imports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ImportTaskResponse]:
    tasks = db.scalars(
        select(ImportTask)
        .where(ImportTask.user_id == current_user.id)
        .order_by(ImportTask.created_at.desc())
    ).all()
    return [_task_response(task) for task in tasks]


@router.get("/imports/{task_id}", response_model=ImportTaskResponse)
def get_import(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportTaskResponse:
    task = db.get(ImportTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return _task_response(task)


@router.post("/imports/{task_id}/retry", response_model=ImportChatResponse, status_code=202)
def retry_import(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportChatResponse:
    task = db.get(ImportTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if task.status != "failed":
        raise HTTPException(status_code=409, detail="任务正在执行，不能重试")
    task.status = "queued"
    task.stage = "queued"
    task.progress = 0
    task.error = None
    db.commit()
    background_tasks.add_task(ImportTaskProcessor().run, task.id)
    return ImportChatResponse(task_id=task.id, import_id=task.id)


@router.get("/messages", response_model=list[MessageResponse])
def list_messages(
    person_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    statement = select(Message).where(Message.user_id == current_user.id)
    if person_id:
        statement = statement.where(Message.person_id == person_id)
    messages = db.scalars(statement.order_by(Message.sent_at, Message.created_at)).all()
    return [
        MessageResponse(
            id=item.id,
            person_id=item.person_id,
            sender_name=item.sender_name,
            direction=item.direction,
            content=item.content,
            sent_at=item.sent_at.isoformat() if item.sent_at else None,
        )
        for item in messages
    ]


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    message = db.get(Message, message_id)
    if not message or message.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    RelationshipEventService().remove_message_evidence(db, message.id)
    db.delete(message)
    db.commit()
    return {"status": "deleted", "message_id": message_id}
