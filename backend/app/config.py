import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_data_dir() -> Path:
    override = os.getenv("RELATIONSHIP_OS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        default_dir = Path(local_app_data) / "RelationshipOS"
    else:
        default_dir = Path.home() / "AppData" / "Local" / "RelationshipOS"
    pointer = default_dir / "data-location.txt"
    if pointer.exists():
        try:
            selected = Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
            if selected.is_absolute():
                return selected.resolve()
        except OSError:
            pass
    return default_dir


def set_data_dir_pointer(target: Path) -> None:
    local_app_data = os.getenv("LOCALAPPDATA")
    default_dir = (
        Path(local_app_data) / "RelationshipOS"
        if local_app_data
        else Path.home() / "AppData" / "Local" / "RelationshipOS"
    )
    default_dir.mkdir(parents=True, exist_ok=True)
    pointer = default_dir / "data-location.txt"
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(str(target.resolve()), encoding="utf-8")
    temporary.replace(pointer)


def _default_database_url() -> str:
    database_path = get_data_dir() / "relationship_os.db"
    return f"sqlite:///{database_path.as_posix()}"


class Settings(BaseSettings):
    app_name: str = "Relationship OS API"
    app_version: str = "0.6.2"
    environment: str = Field(default="development")
    api_prefix: str = Field(default="/api")

    database_url: str = Field(default_factory=_default_database_url)
    redis_url: str = Field(default="redis://localhost:6379/0")
    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="relationship-os")

    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="")
    llm_provider: str = Field(default="openai_compatible")
    llm_model: str = Field(default="mimo-v2.5")
    llm_timeout_seconds: float = Field(default=120.0)
    llm_temperature: float = Field(default=0.2)
    llm_fallback_enabled: bool = Field(default=True)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_timeout_seconds: float = Field(default=45.0)
    ollama_model: str = Field(default="gemma4:e4b")
    embedding_provider: str = Field(default="local")
    embedding_model: str = Field(default="local-hash-v1")
    completion_model: str = Field(default="mimo-v2.5")

    jwt_secret: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    from app.local_config import ensure_jwt_secret, load_local_settings

    settings = Settings()
    local_values = load_local_settings()
    for key, value in local_values.items():
        if key in Settings.model_fields:
            setattr(settings, key, value)
    if not settings.jwt_secret:
        settings.jwt_secret = ensure_jwt_secret()
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
