import io
import time
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.config import get_data_dir
from app.main import app
from app.models import ImportTask, Message, Person
from app.services import import_service


CHAT = """\
小王: [2026-06-01 09:00] 早上好
我: [2026-06-01 09:01] 早上好
小王: [2026-06-01 09:02] 今天一起开会
"""


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/system/auth/register",
        json={"email": f"user-{time.time_ns()}@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _import(client: TestClient, headers: dict[str, str], content: str = CHAT) -> dict:
    response = client.post(
        "/api/chat/import",
        headers=headers,
        data={"self_name": "我"},
        files={"file": ("chat.txt", content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    task = client.get(f"/api/chat/imports/{task_id}", headers=headers)
    assert task.status_code == 200
    assert task.json()["status"] == "completed"
    return task.json()


def test_status_settings_import_dedup_and_delete() -> None:
    with TestClient(app) as client:
        status = client.get("/api/system/status")
        assert status.status_code == 200
        assert status.json()["database"]["dialect"] == "sqlite"
        assert status.json()["initialized"] is True

        headers = _register(client)
        preview = client.post(
            "/api/chat/preview",
            headers=headers,
            files={"file": ("chat.txt", CHAT.encode("utf-8"), "text/plain")},
        )
        assert preview.status_code == 200
        assert preview.json()["message_count"] == 3
        assert preview.json()["sender_names"] == ["小王", "我"]
        oversized = client.post(
            "/api/chat/preview",
            headers=headers,
            files={
                "file": (
                    "oversized.txt",
                    b"x" * (50 * 1024 * 1024 + 1),
                    "text/plain",
                )
            },
        )
        assert oversized.status_code == 413
        saved = client.put(
            "/api/system/settings",
            headers=headers,
            json={
                "llm_api_key": "test-secret-value",
                "llm_base_url": "https://example.invalid/v1",
                "completion_model": "test-model",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["llm_api_key_configured"] is True
        settings = client.get("/api/system/settings", headers=headers).json()
        assert "test-secret-value" not in str(settings)
        assert settings["active_model_provider"] in {"openai_compatible", "ollama"}
        assert settings["active_model_label"]
        assert "fallback_model_label" in settings
        assert settings["remote_configured"] is True
        assert b"test-secret-value" not in (get_data_dir() / "settings.enc").read_bytes()

        first = _import(client, headers)
        assert first["encoding"] == "utf-8"
        assert first["parsed_count"] == 3
        assert first["imported_count"] == 3

        duplicate = _import(client, headers)
        assert duplicate["imported_count"] == 0
        assert duplicate["duplicate_count"] == 3

        with SessionLocal() as db:
            message = db.scalar(select(Message).where(Message.content == "早上好"))
            assert message is not None
            message_id = message.id
        deleted = client.delete(f"/api/chat/messages/{message_id}", headers=headers)
        assert deleted.status_code == 200


def test_failed_ai_stage_rolls_back_messages(monkeypatch) -> None:
    def fail_memories(self, messages):
        raise RuntimeError("synthetic memory failure")

    monkeypatch.setattr(
        import_service.MemoryService,
        "extract_memories",
        fail_memories,
    )
    with TestClient(app) as client:
        headers = _register(client)
        response = client.post(
            "/api/chat/import",
            headers=headers,
            data={"self_name": "我"},
            files={"file": ("chat.txt", CHAT.encode("utf-8"), "text/plain")},
        )
        task = client.get(
            f"/api/chat/imports/{response.json()['task_id']}",
            headers=headers,
        ).json()
        assert task["status"] == "failed"
        assert task["imported_count"] == 0
        assert client.get("/api/person", headers=headers).json() == []


def test_gb18030_import_and_failed_task_retry() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        response = client.post(
            "/api/chat/import",
            headers=headers,
            data={"self_name": "我"},
            files={"file": ("chat.txt", CHAT.encode("gb18030"), "text/plain")},
        )
        task_id = response.json()["task_id"]
        task = client.get(f"/api/chat/imports/{task_id}", headers=headers).json()
        assert task["status"] == "completed"
        assert task["encoding"] == "gb18030"

        invalid = client.post(
            "/api/chat/import",
            headers=headers,
            files={"file": ("invalid.txt", b"not a chat transcript", "text/plain")},
        )
        failed_id = invalid.json()["task_id"]
        failed = client.get(f"/api/chat/imports/{failed_id}", headers=headers).json()
        assert failed["status"] == "failed"
        assert failed["attempts"] == 1
        retried = client.post(
            f"/api/chat/imports/{failed_id}/retry", headers=headers
        )
        assert retried.status_code == 202
        failed_again = client.get(
            f"/api/chat/imports/{failed_id}", headers=headers
        ).json()
        assert failed_again["status"] == "failed"
        assert failed_again["attempts"] == 2


def test_merge_backup_and_restore() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        _import(client, headers)
        second_chat = """\
小张: [2026-06-02 10:00] 项目进展如何
我: [2026-06-02 10:01] 已经完成
小张: [2026-06-02 10:02] 谢谢
"""
        _import(client, headers, second_chat)
        persons = client.get("/api/person", headers=headers).json()
        source = next(item for item in persons if item["name"] == "小张")
        target = next(item for item in persons if item["name"] == "小王")

        merged = client.post(
            "/api/person/merge",
            headers=headers,
            json={
                "source_person_id": source["id"],
                "target_person_id": target["id"],
            },
        )
        assert merged.status_code == 200
        assert len(client.get("/api/person", headers=headers).json()) == 1
        assert client.get("/api/person", headers=headers).json()[0][
            "message_count"
        ] == 6

        backup = client.post(
            "/api/data/backup",
            headers=headers,
            json={"password": "backup-password"},
        )
        assert backup.status_code == 200
        assert backup.content.startswith(b"ROSBACKUP")

        with SessionLocal() as db:
            assert db.scalar(select(ImportTask)) is not None
            message_ids = db.scalars(
                select(Message.id).where(Message.person_id == target["id"])
            ).all()
        for message_id in message_ids:
            assert client.delete(
                f"/api/chat/messages/{message_id}", headers=headers
            ).status_code == 200

        restored = client.post(
            "/api/data/restore",
            headers=headers,
            data={"password": "backup-password"},
            files={
                "file": (
                    "backup.rosbackup",
                    backup.content,
                    "application/vnd.relationship-os.backup",
                )
            },
        )
        assert restored.status_code == 200
        assert restored.json()["persons"] == 1
        restored_person = client.get("/api/person", headers=headers).json()
        assert len(restored_person) == 1
        assert restored_person[0]["message_count"] == len(message_ids)
