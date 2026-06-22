from __future__ import annotations

from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from uuid import uuid4

import httpx
from sqlalchemy import func, select
import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


SYNTHETIC_CHAT = """\
小周: [2026-06-08 09:00] 今天请先整理项目风险清单
我: [2026-06-08 09:02] 好的，我中午前发第一版
小周: [2026-06-08 11:40] 进度怎么样
我: [2026-06-08 11:42] 已完成主要风险和应对方案
小周: [2026-06-08 11:43] 很好，请补充负责人和截止日期
我: [2026-06-08 11:45] 明白，下午两点前更新
小周: [2026-06-08 14:05] 收到了，结构很清楚
我: [2026-06-08 14:06] 谢谢，有变化我会继续同步
"""


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.25)
    raise RuntimeError(f"Backend did not start on {host}:{port}")


def main() -> None:
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import MessageVector, Person, User

    settings = get_settings()
    assert settings.llm_base_url == "https://api.xiaomimimo.com/v1"
    assert settings.completion_model == "mimo-v2.5"
    assert settings.embedding_provider == "local"
    assert settings.llm_api_key

    host = "127.0.0.1"
    port = 8011
    base_url = f"http://{host}:{port}"
    server = uvicorn.Server(
        uvicorn.Config(
            "app.main:app",
            host=host,
            port=port,
            log_level="warning",
        )
    )
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    email = f"mimo-e2e-{uuid4().hex[:12]}@example.com"
    user_id: str | None = None
    try:
        wait_for_port(host, port)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            encoding="utf-8",
            delete=False,
        ) as handle:
            handle.write(SYNTHETIC_CHAT)
            chat_path = Path(handle.name)

        with httpx.Client(
            base_url=base_url,
            timeout=120.0,
            trust_env=False,
        ) as client:
            client.post("/api/system/init").raise_for_status()
            register = client.post(
                "/api/system/auth/register",
                json={"email": email, "password": "mimo-e2e-password"},
            )
            register.raise_for_status()
            register_payload = register.json()
            user_id = register_payload["user_id"]
            headers = {
                "Authorization": f"Bearer {register_payload['access_token']}"
            }

            with chat_path.open("rb") as chat_file:
                imported = client.post(
                    "/api/chat/import",
                    headers=headers,
                    files={"file": ("synthetic-chat.txt", chat_file, "text/plain")},
                )
            imported.raise_for_status()
            assert imported.json()["messages"] == 8

            persons = client.get("/api/person", headers=headers)
            persons.raise_for_status()
            person = persons.json()[0]
            assert person["name"] == "小周"
            assert person["memory_count"] > 0
            person_id = person["id"]

            persona = client.post(
                "/api/person/generate",
                headers=headers,
                json={"contact_id": person_id},
            )
            persona.raise_for_status()
            persona_payload = persona.json()
            assert persona_payload["traits"]
            assert persona_payload["communication"]
            assert 0 <= persona_payload["confidence"] <= 1

            simulation = client.post(
                "/api/simulate",
                headers=headers,
                json={
                    "person_id": person_id,
                    "question": "如果我申请把截止日期延后一天，他可能如何回应？",
                },
            )
            simulation.raise_for_status()
            simulation_payload = simulation.json()
            assert simulation_payload["prediction"]
            assert simulation_payload["reason"]

        with SessionLocal() as db:
            person_row = db.scalar(
                select(Person).where(
                    Person.user_id == user_id,
                    Person.name == "小周",
                )
            )
            assert person_row is not None
            vector_count = db.scalar(
                select(func.count(MessageVector.id)).where(
                    MessageVector.person_id == person_row.id
                )
            )
            assert vector_count == 8

        print(
            {
                "model": settings.completion_model,
                "contact": "小周",
                "messages": 8,
                "memories": person["memory_count"],
                "vectors": vector_count,
                "persona_traits": persona_payload["traits"],
                "predictions": len(simulation_payload["prediction"]),
            }
        )
    finally:
        if "chat_path" in locals():
            chat_path.unlink(missing_ok=True)
        if user_id:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user:
                    db.delete(user)
                    db.commit()
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
