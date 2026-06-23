import json
import os
import ctypes
from ctypes import wintypes
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_data_dir


SETTINGS_FILE = "settings.enc"
KEY_FILE = ".settings.key"
ALLOWED_SETTINGS = {
    "llm_api_key",
    "llm_base_url",
    "llm_provider",
    "llm_model",
    "completion_model",
    "llm_timeout_seconds",
    "llm_temperature",
    "llm_fallback_enabled",
    "ollama_base_url",
    "ollama_timeout_seconds",
    "ollama_model",
    "embedding_provider",
    "embedding_model",
    "web_search_api_key",
    "web_search_base_url",
    "web_search_model",
    "web_search_timeout_seconds",
    "world_import_search_provider",
    "jwt_secret",
}


def _ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _key_path() -> Path:
    return _ensure_data_dir() / KEY_FILE


def _settings_path() -> Path:
    return _ensure_data_dir() / SETTINGS_FILE


def _get_or_create_key() -> bytes:
    path = _key_path()
    if path.exists():
        stored = path.read_bytes()
        if os.name == "nt":
            try:
                return _dpapi_unprotect(stored)
            except OSError:
                if len(stored.strip()) == 44:
                    key = stored.strip()
                    path.write_bytes(_dpapi_protect(key))
                    return key
                raise
        return stored.strip()
    key = Fernet.generate_key()
    path.write_bytes(_dpapi_protect(key) if os.name == "nt" else key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))),
        buffer,
    )


def _dpapi_protect(data: bytes) -> bytes:
    input_blob, input_buffer = _blob(data)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "RelationshipOS",
        None,
        None,
        None,
        1,
        ctypes.byref(output_blob),
    ):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    input_blob, input_buffer = _blob(data)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        1,
        ctypes.byref(output_blob),
    ):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def load_local_settings() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        payload = Fernet(_get_or_create_key()).decrypt(path.read_bytes())
        values = json.loads(payload.decode("utf-8"))
    except (InvalidToken, ValueError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {key: value for key, value in values.items() if key in ALLOWED_SETTINGS}


def save_local_settings(updates: dict[str, Any]) -> dict[str, Any]:
    values = load_local_settings()
    for key, value in updates.items():
        if key not in ALLOWED_SETTINGS:
            continue
        if value is None:
            continue
        values[key] = value
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path = _settings_path()
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_bytes(Fernet(_get_or_create_key()).encrypt(encoded))
    temporary_path.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return values


def ensure_jwt_secret() -> str:
    values = load_local_settings()
    secret = values.get("jwt_secret")
    if isinstance(secret, str) and len(secret) >= 32:
        return secret
    secret = token_urlsafe(48)
    save_local_settings({"jwt_secret": secret})
    return secret
