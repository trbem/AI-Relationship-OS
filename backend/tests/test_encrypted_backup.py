import asyncio
import io
import json
import time
import uuid
import zipfile

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.routes import data as data_routes
from app.main import app
from app.services import backup_service


PASSWORD = "correct horse battery staple"


def test_upload_reader_stops_at_limit() -> None:
    source = io.BytesIO(b"0123456789")
    upload = UploadFile(file=source, filename="oversized.rosbackup")

    with pytest.raises(OverflowError):
        asyncio.run(data_routes._read_backup_upload(upload, max_size=4))

    assert source.tell() == 5


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/system/auth/register",
        json={"email": f"backup-{time.time_ns()}@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload_with_person(client: TestClient, headers: dict[str, str], name: str) -> dict:
    payload = client.get("/api/data/export", headers=headers).json()
    payload["persons"] = [
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "profile_summary": None,
            "confidence": None,
            "created_at": None,
        }
    ]
    return payload


def _seed_person(client: TestClient, headers: dict[str, str], name: str) -> None:
    encrypted = backup_service.create_encrypted_backup(
        _payload_with_person(client, headers, name), PASSWORD
    )
    assert _restore(client, headers, encrypted, PASSWORD).status_code == 200


def _backup(client: TestClient, headers: dict[str, str]) -> bytes:
    response = client.post(
        "/api/data/backup", headers=headers, json={"password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.rosbackup"')
    return response.content


def _restore(
    client: TestClient, headers: dict[str, str], content: bytes, password: str | None
):
    data = {} if password is None else {"password": password}
    return client.post(
        "/api/data/restore",
        headers=headers,
        data=data,
        files={"file": ("backup", content, "application/octet-stream")},
    )


def _legacy(payload: object, name: str = backup_service.LEGACY_ENTRY) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, json.dumps(payload))
    return buffer.getvalue()


def test_encrypted_backup_is_random_and_get_is_gone() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        _seed_person(client, headers, "Alice")
        first = _backup(client, headers)
        second = _backup(client, headers)
        assert first != second
        assert first.startswith(backup_service.MAGIC)
        assert b"Alice" not in first
        assert client.get("/api/data/backup", headers=headers).status_code == 410
        assert client.post(
            "/api/data/backup", headers=headers, json={"password": "too-short"}
        ).status_code == 422


def test_correct_restore_and_failures_are_atomic() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        _seed_person(client, headers, "Before")
        encrypted = _backup(client, headers)
        baseline = client.get("/api/data/export", headers=headers).json()["persons"]

        variants = [
            (encrypted, "wrong password value"),
            (encrypted[:-8] + bytes([encrypted[-8] ^ 1]) + encrypted[-7:], PASSWORD),
            (encrypted[:-10], PASSWORD),
        ]
        for content, password in variants:
            response = _restore(client, headers, content, password)
            assert response.status_code == 400
            assert client.get("/api/data/export", headers=headers).json()["persons"] == baseline

        restored = _restore(client, headers, encrypted, PASSWORD)
        assert restored.status_code == 200
        assert restored.json()["legacy_unencrypted"] is False
        assert [p["name"] for p in client.get("/api/person", headers=headers).json()] == [
            "Before"
        ]


def test_legacy_zip_compatibility_and_archive_validation() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        payload = _payload_with_person(client, headers, "Legacy")
        response = _restore(client, headers, _legacy(payload), None)
        assert response.status_code == 200
        assert response.json()["legacy_unencrypted"] is True

        assert _restore(client, headers, _legacy(payload, "../backup.json"), None).status_code == 400
        duplicate = io.BytesIO()
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr(backup_service.LEGACY_ENTRY, "{}")
            archive.writestr("extra.json", "{}")
        assert _restore(client, headers, duplicate.getvalue(), None).status_code == 400


def test_size_and_compression_ratio_limits(monkeypatch) -> None:
    original_upload_limit = backup_service.MAX_UPLOAD_SIZE
    monkeypatch.setattr(backup_service, "MAX_UPLOAD_SIZE", 4)
    try:
        backup_service.parse_backup(b"12345", None)
        assert False, "upload limit was not enforced"
    except OverflowError:
        pass
    monkeypatch.setattr(backup_service, "MAX_UPLOAD_SIZE", original_upload_limit)

    payload = {"format": "relationship-os-backup", "version": 3}
    bomb = _legacy(payload | {"padding": "x" * 10_000})
    monkeypatch.setattr(backup_service, "MAX_COMPRESSION_RATIO", 2)
    try:
        backup_service.parse_backup(bomb, None)
        assert False, "compression ratio limit was not enforced"
    except backup_service.BackupError:
        pass
