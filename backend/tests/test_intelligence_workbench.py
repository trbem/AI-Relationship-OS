import json
import time

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Message, Person
from app.services.ai_client import AIClient
from app.services.relationship_event_service import RelationshipEventService


def _register(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/system/auth/register",
        json={
            "email": f"intelligence-{time.time_ns()}@example.com",
            "password": "password123",
        },
    )
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload["user_id"]


def _person(user_id: str, name: str = "Alice") -> str:
    with SessionLocal() as db:
        person = Person(user_id=user_id, name=name)
        db.add(person)
        db.flush()
        messages = [
            Message(
                user_id=user_id,
                person_id=person.id,
                sender_name=name,
                direction="inbound",
                content="I support the plan and will help you finish it.",
            ),
            Message(
                user_id=user_id,
                person_id=person.id,
                sender_name=name,
                direction="inbound",
                content="Please send the progress before we decide.",
            ),
            Message(
                user_id=user_id,
                person_id=person.id,
                sender_name=name,
                direction="inbound",
                content="Sorry, I cannot agree without more context.",
            ),
        ]
        db.add_all(messages)
        db.flush()
        RelationshipEventService().extract_incremental(
            db,
            user_id=user_id,
            person_id=person.id,
            message_ids=[item.id for item in messages],
        )
        db.commit()
        return person.id


def test_evidence_session_graph_report_and_group_workflow() -> None:
    with TestClient(app) as client:
        headers, user_id = _register(client)
        alice_id = _person(user_id)
        bob_id = _person(user_id, "Bob")

        one_shot = client.post(
            "/api/simulate",
            headers=headers,
            json={"person_id": alice_id, "question": "Can we delay one day?"},
        )
        assert one_shot.status_code == 200
        result = one_shot.json()
        assert result["prediction"]
        assert result["evidence"]
        assert 0 <= result["confidence_summary"]["score"] <= 1
        assert result["prediction"][0]["evidence_ids"]

        created = client.post(
            "/api/simulate/sessions",
            headers=headers,
            json={
                "person_id": alice_id,
                "question": "Can we delay one day?",
                "title": "Deadline discussion",
            },
        )
        assert created.status_code == 201
        session = created.json()
        assert len(session["messages"]) == 2
        session_id = session["id"]

        follow_up = client.post(
            f"/api/simulate/sessions/{session_id}/messages",
            headers=headers,
            json={"content": "What wording may reduce concern?"},
        )
        assert follow_up.status_code == 201
        assert follow_up.json()["payload"]["evidence"]

        graph = client.get(
            "/api/graph/knowledge-map?days=3650",
            headers=headers,
        )
        assert graph.status_code == 200
        assert any(node["type"] == "event" for node in graph.json()["nodes"])
        person_node = next(
            node for node in graph.json()["nodes"] if node["id"] == alice_id
        )
        assert person_node["score_components"]
        assert person_node["change_reasons"]

        for label, wording in [
            ("Direct", "Please approve a one-day delay."),
            ("Context first", "I have completed most work; may I use one more day?"),
        ]:
            scenario = client.post(
                f"/api/simulate/sessions/{session_id}/scenarios",
                headers=headers,
                json={
                    "label": label,
                    "wording": wording,
                    "timing": "morning",
                    "channel": "chat",
                    "goal": "secure a one-day delay",
                },
            )
            assert scenario.status_code == 201

        comparison = client.post(
            f"/api/simulate/sessions/{session_id}/compare",
            headers=headers,
        )
        assert len(comparison.json()["comparison"]) == 2

        report = client.post(
            "/api/reports",
            headers=headers,
            json={"session_id": session_id},
        )
        assert report.status_code == 201
        report_id = report.json()["id"]
        pdf = client.get(
            f"/api/reports/{report_id}/export?format=pdf",
            headers=headers,
        )
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

        group = client.post(
            "/api/group-simulations",
            headers=headers,
            json={
                "primary_person_id": alice_id,
                "participant_ids": [alice_id, bob_id],
                "title": "Small team impact",
                "goal": "Evaluate a schedule change",
                "rounds": 3,
            },
        )
        assert group.status_code == 201
        group_id = group.json()["id"]
        run = client.post(
            f"/api/group-simulations/{group_id}/run",
            headers=headers,
        )
        assert run.status_code == 200
        rounds = run.json()["rounds"]
        assert len(rounds) == 3
        assert all(item["people"][0]["simulated"] is True for item in rounds)

        backup = client.get("/api/data/export", headers=headers).json()
        assert backup["version"] == 3
        assert backup["simulation_sessions"]
        assert backup["relationship_events"]
        assert backup["strategy_reports"]
        assert backup["group_simulations"]
        json.dumps(backup)


def test_ai_connection_endpoint_uses_supplied_remote_config(monkeypatch) -> None:
    captured: dict[str, str | float] = {}

    def fake_test(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float | None = None,
    ) -> dict:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
                "timeout_seconds": timeout_seconds,
                "temperature": temperature if temperature is not None else -1,
            }
        )
        return {
            "provider": "openai_compatible",
            "model": model,
            "message": "ok",
        }

    monkeypatch.setattr(AIClient, "test_openai_compatible_connection", fake_test)
    with TestClient(app) as client:
        headers, _ = _register(client)
        response = client.post(
            "/api/system/ai/test-connection",
            headers=headers,
            json={
                "llm_provider": "openai_compatible",
                "llm_base_url": "https://api.xiaomimimo.com/v1",
                "llm_api_key": "sk-test-key",
                "llm_model": "mimo-v2.5",
                "llm_timeout_seconds": 45,
                "llm_temperature": 0.1,
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["provider"] == "openai_compatible"
        assert response.json()["message"] == "ok"
        assert captured == {
            "base_url": "https://api.xiaomimimo.com/v1",
            "api_key": "sk-test-key",
            "model": "mimo-v2.5",
            "timeout_seconds": 45.0,
            "temperature": 0.1,
        }
