import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.services import backup_service
from app.services.backup_service import BackupError, create_encrypted_backup, parse_backup
from app.services.data_restore_service import build_user_export, restore_payload


router = APIRouter()
BACKUP_READ_CHUNK_SIZE = 1024 * 1024


class BackupRequest(BaseModel):
    password: str = Field(min_length=10)


async def _read_backup_upload(file: UploadFile, max_size: int) -> bytes:
    content = bytearray()
    while True:
        remaining = max_size - len(content)
        chunk = await file.read(min(BACKUP_READ_CHUNK_SIZE, remaining + 1))
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > max_size:
            raise OverflowError(f"备份文件不能超过 {max_size // (1024 * 1024)} MB")


@router.get("/export")
def export_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    return JSONResponse(
        build_user_export(db, current_user.id),
        headers={"Content-Disposition": 'attachment; filename="relationship-os-export.json"'},
    )


@router.get("/backup")
def deprecated_backup() -> None:
    raise HTTPException(
        status_code=410,
        detail="明文备份已停用，请升级客户端并使用 POST /api/data/backup 创建加密备份",
    )


@router.post("/backup")
def backup_data(
    request: BackupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    encrypted = create_encrypted_backup(build_user_export(db, current_user.id), request.password)
    return StreamingResponse(
        io.BytesIO(encrypted),
        media_type="application/vnd.relationship-os.backup",
        headers={"Content-Disposition": 'attachment; filename="relationship-os-backup.rosbackup"'},
    )


@router.post("/restore")
async def restore_data(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | str | bool]:
    try:
        raw = await _read_backup_upload(file, backup_service.MAX_UPLOAD_SIZE)
        parsed = parse_backup(raw, password)
        result = restore_payload(parsed.payload, db, current_user)
    except OverflowError as exc:
        db.rollback()
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except (BackupError, HTTPException) as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="备份数据不完整或存在冲突") from exc
    result["legacy_unencrypted"] = parsed.legacy_unencrypted
    return result
