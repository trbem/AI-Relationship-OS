from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys
import threading
import time
from uuid import uuid4

import httpx
from sqlalchemy import func, select
import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.25)
    raise RuntimeError(f"Backend did not start on {host}:{port}")


def run_flow(
    *,
    base_url: str,
    file_path: Path,
    self_name: str | None,
    expected_self_sender: str,
) -> dict:
    from app.db import SessionLocal
    from app.models import Message, MessageVector, Person, PersonMemory, SimulationLog

    email = f"e2e-{uuid4().hex[:12]}@example.com"
    password = "e2e-password"

    with httpx.Client(base_url=base_url, timeout=60.0, trust_env=False) as client:
        init_response = client.post("/api/system/init")
        init_response.raise_for_status()

        register_response = client.post(
            "/api/system/auth/register",
            json={"email": email, "password": password},
        )
        register_response.raise_for_status()
        token = register_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        form_data = {"self_name": self_name} if self_name else {}
        with file_path.open("rb") as chat_file:
            import_response = client.post(
                "/api/chat/import",
                headers=headers,
                data=form_data,
                files={"file": (file_path.name, chat_file, "text/plain")},
            )
        import_response.raise_for_status()
        import_payload = import_response.json()
        assert import_payload["contacts"] == 1
        assert import_payload["messages"] == 119

        persons_response = client.get("/api/person", headers=headers)
        persons_response.raise_for_status()
        persons = persons_response.json()
        assert len(persons) == 1
        assert persons[0]["name"] == "小王"
        assert persons[0]["message_count"] == 119
        assert persons[0]["memory_count"] > 0
        person_id = persons[0]["id"]

        detail_response = client.get(f"/api/person/{person_id}", headers=headers)
        detail_response.raise_for_status()
        detail = detail_response.json()
        assert len(detail["messages"]) == 119
        assert len(detail["memories"]) > 0
        assert len(detail["vector_refs"]) == 119

        graph_response = client.get(
            "/api/graph/relationship-map",
            headers=headers,
        )
        graph_response.raise_for_status()
        graph = graph_response.json()
        assert any(
            node["type"] == "person" and node["name"] == "小王"
            for node in graph["nodes"]
        )

        simulation_response = client.post(
            "/api/simulate",
            headers=headers,
            json={
                "person_id": person_id,
                "question": "我想申请两天假，他可能会怎么回应？",
            },
        )
        simulation_response.raise_for_status()
        simulation = simulation_response.json()
        assert simulation["prediction"]
        assert simulation["reason"]

    with SessionLocal() as db:
        person = db.scalar(
            select(Person).where(Person.user_id == register_response.json()["user_id"])
        )
        assert person is not None
        directions = dict(
            db.execute(
                select(Message.direction, func.count(Message.id))
                .where(Message.person_id == person.id)
                .group_by(Message.direction)
            ).all()
        )
        assert directions == {"inbound": 68, "outbound": 51}

        self_sender_count = db.scalar(
            select(func.count(Message.id)).where(
                Message.person_id == person.id,
                Message.sender_name == expected_self_sender,
                Message.direction == "outbound",
            )
        )
        assert self_sender_count == 51

        memory_count = db.scalar(
            select(func.count(PersonMemory.id)).where(
                PersonMemory.person_id == person.id
            )
        )
        vector_count = db.scalar(
            select(func.count(MessageVector.id)).where(
                MessageVector.person_id == person.id
            )
        )
        simulation_count = db.scalar(
            select(func.count(SimulationLog.id)).where(
                SimulationLog.person_id == person.id
            )
        )
        assert memory_count and memory_count > 0
        assert vector_count == 119
        assert simulation_count == 1

    return {
        "email": email,
        "user_id": register_response.json()["user_id"],
        "person_id": person_id,
        "contact": "小王",
        "messages": 119,
        "inbound": 68,
        "outbound": 51,
        "memories": memory_count,
        "vectors": vector_count,
        "simulation_logs": simulation_count,
    }


def cleanup_flow(result: dict) -> None:
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.get(User, result["user_id"])
        if user:
            db.delete(user)
            db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--temporary", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()

    os.environ["LLM_BASE_URL"] = ""
    os.environ["LLM_API_KEY"] = ""
    os.environ["LLM_FALLBACK_ENABLED"] = "false"
    os.environ["ENCRYPTION_KEY"] = "e2e-only-key-with-at-least-32-bytes"

    host = "127.0.0.1"
    base_url = f"http://{host}:{args.port}"
    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=args.port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        wait_for_port(host, args.port)
        original_result = run_flow(
            base_url=base_url,
            file_path=args.original,
            self_name="小李",
            expected_self_sender="小李",
        )
        temporary_result = run_flow(
            base_url=base_url,
            file_path=args.temporary,
            self_name=None,
            expected_self_sender="我",
        )
        print({"original_with_self_name": original_result})
        print({"temporary_with_self_alias": temporary_result})
        cleanup_flow(original_result)
        cleanup_flow(temporary_result)
        print("e2e test data cleaned")
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
