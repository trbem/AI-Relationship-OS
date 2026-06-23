import os
import shutil
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.auth.jwt_handler import create_access_token
from app.auth.dependencies import get_current_user
from app.config import (
    get_data_dir,
    get_settings,
    reload_settings,
    set_data_dir_pointer,
)
from app.db import engine, get_db, init_db
from app.local_config import save_local_settings
from app.models import User
from app.schemas import (
    ConnectionTestRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SettingsUpdateRequest,
)
from app.services.ai_client import AIClient, AIClientError
from app.services.openai_web_search_service import OpenAIWebSearchService, WorldImportError

router = APIRouter()


def _settings_response() -> dict:
    settings = get_settings()
    model = settings.llm_model or settings.completion_model
    remote_configured = bool(settings.llm_base_url and settings.llm_api_key)
    provider = settings.llm_provider
    if provider == "openai_compatible" and not remote_configured:
        provider = "ollama"
    active_provider = provider
    if provider == "openai_compatible":
        active_model = model
        active_label = f"OpenAI 兼容 · {model}"
    else:
        active_model = settings.ollama_model
        active_label = f"Ollama · {settings.ollama_model}"
    fallback_label = (
        f"Ollama 兜底 · {settings.ollama_model}"
        if settings.llm_fallback_enabled and settings.ollama_model
        else "未启用"
    )
    return {
        "llm_api_key_configured": bool(settings.llm_api_key),
        "llm_provider": provider,
        "llm_base_url": settings.llm_base_url,
        "llm_model": model,
        "completion_model": settings.completion_model,
        "active_model_provider": active_provider,
        "active_model": active_model,
        "active_model_label": active_label,
        "fallback_model_label": fallback_label,
        "remote_configured": remote_configured,
        "llm_timeout_seconds": settings.llm_timeout_seconds,
        "llm_temperature": settings.llm_temperature,
        "llm_fallback_enabled": settings.llm_fallback_enabled,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_timeout_seconds": settings.ollama_timeout_seconds,
        "ollama_model": settings.ollama_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "web_search_api_key_configured": bool(settings.web_search_api_key),
        "web_search_base_url": settings.web_search_base_url,
        "web_search_model": settings.web_search_model,
        "web_search_timeout_seconds": settings.web_search_timeout_seconds,
        "world_import_search_provider": settings.world_import_search_provider,
        "data_directory": str(get_data_dir()),
    }


def _migrate_data_directory(value: str) -> bool:
    if os.getenv("RELATIONSHIP_OS_DATA_DIR"):
        raise HTTPException(
            status_code=409,
            detail="数据目录由 RELATIONSHIP_OS_DATA_DIR 管理，不能在应用内修改",
        )
    if engine.dialect.name != "sqlite":
        raise HTTPException(
            status_code=409,
            detail="仅 SQLite 单机模式支持迁移本地数据目录",
        )
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="数据目录必须是绝对路径")
    target = target.resolve()
    current = get_data_dir().resolve()
    if target == current:
        return False
    target.mkdir(parents=True, exist_ok=True)
    destination_db = target / "relationship_os.db"
    raw = engine.raw_connection()
    destination = sqlite3.connect(destination_db)
    try:
        raw.driver_connection.backup(destination)
    finally:
        destination.close()
        raw.close()
    for filename in (".settings.key", "settings.enc"):
        source = current / filename
        if source.exists():
            shutil.copy2(source, target / filename)
    source_imports = current / "imports"
    if source_imports.exists():
        shutil.copytree(
            source_imports,
            target / "imports",
            dirs_exist_ok=True,
        )
    set_data_dir_pointer(target)
    return True


def _hash_password(password: str) -> str:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64, os

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = base64.b64encode(kdf.derive(password.encode()))
    return base64.b64encode(salt).decode() + "$" + key.decode()


def _verify_password(password: str, stored: str) -> bool:
    import base64, os
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    try:
        salt_b64, key_b64 = stored.split("$", 1)
    except ValueError:
        return False

    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    try:
        kdf.verify(password.encode(), base64.b64decode(key_b64))
        return True
    except Exception:
        return False


@router.post("/init")
def initialize_system() -> dict[str, str]:
    init_db()
    return {"status": "ok", "detail": "database tables initialized"}


@router.get("/status")
def system_status() -> dict:
    settings = get_settings()
    database_ok = False
    error: str | None = None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        error = type(exc).__name__
    initialized = "users" in inspect(engine).get_table_names() if database_ok else False
    return {
        "status": "ok" if database_ok else "degraded",
        "version": settings.app_version,
        "initialized": initialized,
        "database": {
            "status": "ok" if database_ok else "error",
            "dialect": engine.dialect.name,
            "error": error,
        },
        "ai": {
            "remote_configured": bool(settings.llm_base_url and settings.llm_api_key),
            "model": settings.completion_model,
            "ollama_fallback_enabled": settings.llm_fallback_enabled,
            "embedding_provider": settings.embedding_provider,
        },
        "data_dir": str(get_data_dir()),
    }


@router.get("/settings")
def get_local_settings(current_user: User = Depends(get_current_user)) -> dict:
    return _settings_response()


@router.put("/settings")
def update_local_settings(
    request: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    updates = request.model_dump(exclude_unset=True)
    current = get_settings()
    requested_data_directory = updates.pop("data_directory", None)
    provider = str(updates.get("llm_provider", current.llm_provider)).strip().lower()
    if "llm_api_key" in updates:
        updates["llm_api_key"] = updates["llm_api_key"].strip()
        if not updates["llm_api_key"]:
            updates.pop("llm_api_key")
    effective_api_key = str(updates.get("llm_api_key", current.llm_api_key)).strip()
    effective_base_url = str(updates.get("llm_base_url", current.llm_base_url)).strip()
    if provider == "openai_compatible":
        if not effective_api_key:
            raise HTTPException(
                status_code=400,
                detail="OpenAI-compatible API key is required",
            )
        if not effective_base_url:
            raise HTTPException(
                status_code=400,
                detail="OpenAI-compatible base URL is required",
            )
    if "llm_model" in updates and "completion_model" not in updates:
        updates["completion_model"] = updates["llm_model"]
    if "completion_model" in updates and "llm_model" not in updates:
        updates["llm_model"] = updates["completion_model"]
    save_local_settings(updates)
    restart_required = False
    if requested_data_directory:
        restart_required = _migrate_data_directory(requested_data_directory)
    reload_settings()
    return {
        "status": "saved",
        "restart_required": restart_required,
        **_settings_response(),
    }


@router.post("/ai/test-connection")
def test_ai_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    updates = request.model_dump(exclude_unset=True)
    provider = str(updates.get("llm_provider", settings.llm_provider)).strip().lower()
    base_url = str(updates.get("llm_base_url", settings.llm_base_url)).strip()
    api_key = str(updates.get("llm_api_key", settings.llm_api_key)).strip()
    model = str(
        updates.get(
            "llm_model",
            settings.llm_model or settings.completion_model,
        )
    ).strip()
    timeout_seconds = float(updates.get("llm_timeout_seconds", settings.llm_timeout_seconds))
    temperature = updates.get("llm_temperature", settings.llm_temperature)
    ollama_base_url = str(updates.get("ollama_base_url", settings.ollama_base_url)).strip()
    ollama_model = str(updates.get("ollama_model", settings.ollama_model)).strip()
    ollama_timeout_seconds = float(
        updates.get("ollama_timeout_seconds", settings.ollama_timeout_seconds)
    )

    client = AIClient()
    try:
        if provider == "ollama":
            result = client.test_ollama_connection(
                base_url=ollama_base_url,
                model=ollama_model,
                timeout_seconds=ollama_timeout_seconds,
                temperature=temperature,
            )
        else:
            result = client.test_openai_compatible_connection(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
            )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "provider": provider,
        "base_url": base_url if provider != "ollama" else ollama_base_url,
        "model": result["model"],
        "message": result["message"],
    }


@router.post("/ai/test-web-search")
def test_web_search_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    updates = request.model_dump(exclude_unset=True)
    try:
        return OpenAIWebSearchService().test_connection(
            api_key=str(updates.get("web_search_api_key", settings.web_search_api_key)),
            base_url=str(updates.get("web_search_base_url", settings.web_search_base_url)),
            model=str(updates.get("web_search_model", settings.web_search_model)),
            timeout_seconds=float(
                updates.get(
                    "web_search_timeout_seconds",
                    settings.web_search_timeout_seconds,
                )
            ),
        )
    except WorldImportError as exc:
        raise HTTPException(status_code=400, detail=exc.detail.to_dict()) from exc


@router.post("/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> LoginResponse:
    existing = db.scalar(select(User).where(User.email == request.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=request.email,
        password_hash=_hash_password(request.password),
    )
    db.add(user)
    db.flush()

    token = create_access_token(user.id)
    db.commit()
    return LoginResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == request.email))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not _verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return LoginResponse(access_token=token, user_id=user.id, email=user.email)


@router.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }
