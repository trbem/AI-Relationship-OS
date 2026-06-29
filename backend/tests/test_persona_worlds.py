import time

from fastapi.testclient import TestClient

from app.main import app
from app.services.free_web_search_service import FreeWebWorldSearchService
from app.services.openai_web_search_service import OpenAIWebSearchService
from app.services.world_ai_service import WorldAIService, _fallback_import_payload_v2
from app.services.world_import_service import WorldImportService


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/system/auth/register",
        json={
            "email": f"worlds-{time.time_ns()}@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _world(client: TestClient, headers: dict[str, str], name: str = "测试世界") -> str:
    response = client.post(
        "/api/worlds",
        headers=headers,
        json={"name": name, "theme": "测试", "world_background": "独立的角色沙盘。"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _wait_world_import(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    for _ in range(30):
        response = client.get(f"/api/world-imports/{task_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] not in {"queued", "running", "searching", "extracting"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("world import task did not finish")


def test_manual_world_graph_simulation_and_export() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        ids = []
        for name, faction in (("Alice", "A"), ("Bob", "B")):
            response = client.post(
                f"/api/worlds/{world_id}/personas",
                headers=headers,
                json={
                    "name": name,
                    "summary": f"{name} profile",
                    "traits": ["璋ㄦ厧"],
                    "motivations": ["瀹屾垚鐩爣"],
                    "faction": faction,
                },
            )
            assert response.status_code == 201
            ids.append(response.json()["id"])
        relationship = client.post(
            f"/api/worlds/{world_id}/relationships",
            headers=headers,
            json={
                "source_persona_id": ids[0],
                "target_persona_id": ids[1],
                "relationship_type": "鍚堜綔",
                "strength": 0.8,
            },
        )
        assert relationship.status_code == 201

        graph = client.get(f"/api/worlds/{world_id}/graph", headers=headers)
        assert graph.status_code == 200
        assert len(graph.json()["nodes"]) == 2
        assert all(node["type"] == "persona" for node in graph.json()["nodes"])
        assert not any(node["name"] == "Ghost" for node in graph.json()["nodes"])

        simulation = client.post(
            f"/api/worlds/{world_id}/simulations",
            headers=headers,
            json={
                "title": "Negotiation",
                "scenario": "Two people need to decide whether to cooperate.",
                "participant_ids": ids,
                "rounds": 5,
            },
        )
        assert simulation.status_code == 201
        result = simulation.json()
        assert result["mode"] == "role_sandbox"
        assert len(result["rounds"]) == 5
        assert "evidence" not in str(result).lower()
        assert "真实人物" in result["disclaimer"]
        assert result["setting_completeness"] >= 0
        promoted = client.post(
            f"/api/worlds/{world_id}/simulations/{result['id']}/promote",
            headers=headers,
            json={
                "round_number": 1,
                "title": "达成共识",
                "summary": "沙盘中形成的衍生事件。",
            },
        )
        assert promoted.status_code == 201
        assert promoted.json()["label"] == "\u865a\u6784\u884d\u751f\u5185\u5bb9"

        exported = client.get(f"/api/worlds/{world_id}/export", headers=headers)
        assert exported.status_code == 200
        imported = client.post("/api/worlds/import", headers=headers, json=exported.json())
        assert imported.status_code == 201
        assert imported.json()["persona_count"] == 2

        backup = client.get("/api/data/export", headers=headers)
        assert backup.status_code == 200
        assert backup.json()["version"] == 3
        assert len(backup.json()["persona_worlds"]) == 2


def test_curated_versions_are_separate_and_limited() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        catalog = client.get("/api/persona-catalog", headers=headers)
        assert catalog.status_code == 200
        templates = {item["id"]: item for item in catalog.json()}
        assert set(templates) == {
            "three_kingdoms_romance_v1",
            "three_kingdoms_history_v1",
            "water_margin_v1",
            "journey_to_the_west_v1",
            "dream_of_the_red_chamber_v1",
        }

        romance_id = _world(client, headers, "婕斾箟")
        history_id = _world(client, headers, "鍘嗗彶")
        water_margin_id = _world(client, headers, "姘存祾")
        journey_id = _world(client, headers, "瑗挎父")
        red_chamber_id = _world(client, headers, "绾㈡ゼ")
        romance = client.post(
            f"/api/worlds/{romance_id}/import/catalog",
            headers=headers,
            json={
                "template_id": "three_kingdoms_romance_v1",
                "limit": 8,
                "core_persona_keys": ["liu_bei"],
            },
        )
        history = client.post(
            f"/api/worlds/{history_id}/import/catalog",
            headers=headers,
            json={
                "template_id": "three_kingdoms_history_v1",
                "limit": 8,
                "core_persona_keys": ["cao_cao"],
            },
        )
        assert romance.status_code == history.status_code == 200
        romance_names = {item["name"] for item in romance.json()["world"]["personas"]}
        history_names = {item["name"] for item in history.json()["world"]["personas"]}
        assert len(romance_names) <= 8
        assert len(history_names) <= 8
        assert "璨傝潐" not in history_names
        assert all(
            item["source_ref"].startswith("three_kingdoms_romance_v1:")
            for item in romance.json()["world"]["personas"]
        )
        assert all(
            item["source_ref"].startswith("three_kingdoms_history_v1:")
            for item in history.json()["world"]["personas"]
        )

        water_margin = client.post(
            f"/api/worlds/{water_margin_id}/import/catalog",
            headers=headers,
            json={
                "template_id": "water_margin_v1",
                "limit": 8,
                "core_persona_keys": ["song_jiang"],
            },
        )
        journey = client.post(
            f"/api/worlds/{journey_id}/import/catalog",
            headers=headers,
            json={
                "template_id": "journey_to_the_west_v1",
                "limit": 8,
                "core_persona_keys": ["tang_seng"],
            },
        )
        red_chamber = client.post(
            f"/api/worlds/{red_chamber_id}/import/catalog",
            headers=headers,
            json={
                "template_id": "dream_of_the_red_chamber_v1",
                "limit": 8,
                "core_persona_keys": ["jia_baoyu"],
            },
        )
        assert (
            water_margin.status_code
            == journey.status_code
            == red_chamber.status_code
            == 200
        )
        assert len(water_margin.json()["world"]["personas"]) <= 8
        assert len(journey.json()["world"]["personas"]) <= 8
        assert len(red_chamber.json()["world"]["personas"]) <= 8
        assert all(
            item["source_ref"].startswith("water_margin_v1:")
            for item in water_margin.json()["world"]["personas"]
        )
        assert all(
            item["source_ref"].startswith("journey_to_the_west_v1:")
            for item in journey.json()["world"]["personas"]
        )
        assert all(
            item["source_ref"].startswith("dream_of_the_red_chamber_v1:")
            for item in red_chamber.json()["world"]["personas"]
        )


def test_online_preview_confirm_deduplicates(monkeypatch) -> None:
    def fake_search(self, query: str, limit: int, language: str = "zh") -> dict:
        return {
            "query": query,
            "partial": True,
            "errors": ["secondary source unavailable"],
            "relationships": [],
            "candidates": [
                {
                    "id": "Q123",
                    "name": "Example Character",
                    "summary": "Source-backed summary.",
                    "aliases": ["Example"],
                    "verification_status": "web_verified",
                    "sources": [
                        {
                            "source_type": "wikidata",
                            "external_id": "Q123",
                            "url": "https://www.wikidata.org/wiki/Q123",
                            "title": "Example Character",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(OpenAIWebSearchService, "search_world", fake_search)
    monkeypatch.setattr(FreeWebWorldSearchService, "search_world", fake_search)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "绀轰緥", "limit": 20},
        )
        assert preview.status_code == 202
        task = _wait_world_import(client, headers, preview.json()["id"])
        assert task["status"] == "partial"
        task_id = task["id"]
        confirmed = client.post(
            f"/api/world-imports/{task_id}/confirm",
            headers=headers,
            json={"world_id": world_id, "candidate_ids": ["Q123"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["imported_personas"] == 1
        repeated = client.post(
            f"/api/world-imports/{task_id}/confirm",
            headers=headers,
            json={"world_id": world_id, "candidate_ids": ["Q123"]},
        )
        assert repeated.status_code == 409
        detail = client.get(f"/api/worlds/{world_id}", headers=headers).json()
        assert detail["persona_count"] == 1
        assert detail["personas"][0]["source_type"] == "openai_web_search"


def test_online_preview_uses_generated_fallback_and_imports_relationships(monkeypatch) -> None:
    def empty_search(self, query: str, limit: int, language: str = "zh") -> dict:
        return {
            "query": query,
            "partial": True,
            "errors": ["network blocked"],
            "source_failures": [{"source": "wikidata", "stage": "search", "status": 403}],
            "candidates": [],
            "relationships": [],
        }

    def generated(self, query: str, limit: int, *, source_failures=None) -> dict:
        return {
            "query": query,
            "partial": True,
            "fallback_mode": "model_generated",
            "generated_notice": "AI generated",
            "source_failures": source_failures or [],
            "candidates": [
                {
                    "id": "generated:liu-bei",
                    "name": "刘备",
                    "summary": "蜀汉核心人物",
                    "source_type": "generated_unverified",
                    "verification_status": "generated_unverified",
                    "faction": "蜀汉",
                    "traits": ["仁厚"],
                    "motivations": ["复兴汉室"],
                    "sources": [],
                },
                {
                    "id": "generated:guan-yu",
                    "name": "关羽",
                    "summary": "刘备重要盟友",
                    "source_type": "generated_unverified",
                    "verification_status": "generated_unverified",
                    "faction": "蜀汉",
                    "sources": [],
                },
            ],
            "relationships": [
                {
                    "source": "generated:liu-bei",
                    "target": "generated:guan-yu",
                    "type": "盟友",
                    "directed": True,
                    "strength": 0.9,
                    "description": "桃园结义关系",
                    "confidence": 0.45,
                    "source_type": "generated_unverified",
                    "source_ref": None,
                }
            ],
        }

    monkeypatch.setattr(OpenAIWebSearchService, "search_world", empty_search)
    monkeypatch.setattr(FreeWebWorldSearchService, "search_world", empty_search)
    monkeypatch.setattr(WorldAIService, "generated_import_preview", generated)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "三国人物", "limit": 20},
        )
        assert preview.status_code == 202
        task = _wait_world_import(client, headers, preview.json()["id"])
        fallback = client.post(
            f'/api/world-imports/{task["id"]}/generate-fallback',
            headers=headers,
            json={"mode": "generate_missing", "target_count": 20},
        )
        assert fallback.status_code == 200
        task = fallback.json()
        result = task["result"]
        assert result["fallback_mode"] == "model_generated"
        assert not result["candidates"][0]["sources"]
        confirmed = client.post(
            f'/api/world-imports/{task["id"]}/confirm',
            headers=headers,
            json={
                "world_id": world_id,
                "candidate_ids": ["generated:liu-bei", "generated:guan-yu"],
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["imported_relationships"] == 1


def test_world_import_defaults_to_free_web_provider(monkeypatch) -> None:
    def fake_search(self, query: str, limit: int, language: str = "zh") -> dict:
        return {
            "query": query,
            "provider": "free_web",
            "source_type": "free_web",
            "partial": False,
            "errors": [],
            "source_failures": [],
            "relationships": [],
            "candidates": [
                {
                    "id": "free-web-alice",
                    "name": "Alice",
                    "summary": "Source-backed summary.",
                    "source_type": "free_web",
                    "source_ref": "free-web-alice",
                    "verification_status": "web_verified",
                    "sources": [
                        {
                            "source_type": "free_web",
                            "url": "https://example.test/alice",
                            "title": "Alice",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "search_world", fake_search)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "Example World", "limit": 20},
        )
        assert preview.status_code == 202
        task = _wait_world_import(client, headers, preview.json()["id"])
        assert task["status"] == "preview"
        assert task["result"]["provider"] == "free_web"
        confirmed = client.post(
            f'/api/world-imports/{task["id"]}/confirm',
            headers=headers,
            json={"world_id": world_id, "candidate_ids": ["free-web-alice"]},
        )
        assert confirmed.status_code == 200
        detail = client.get(f"/api/worlds/{world_id}", headers=headers).json()
        assert detail["personas"][0]["source_type"] == "free_web"


def test_world_import_passes_language_to_free_web(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake_search(self, query: str, limit: int, language: str = "zh") -> dict:
        seen["language"] = language
        return {
            "query": query,
            "provider": "free_web",
            "source_type": "free_web",
            "language": language,
            "partial": False,
            "errors": [],
            "source_failures": [],
            "relationships": [],
            "candidates": [
                {
                    "id": "free-web-alice",
                    "name": "Alice",
                    "summary": "Source-backed summary.",
                    "source_type": "free_web",
                    "source_ref": "free-web-alice",
                    "verification_status": "web_verified",
                    "sources": [
                        {
                            "source_type": "free_web",
                            "url": "https://example.test/alice",
                            "title": "Alice",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "search_world", fake_search)
    with TestClient(app) as client:
        headers = _register(client)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "Three Kingdoms", "limit": 20, "language": "en"},
        )
        assert preview.status_code == 202
        task = _wait_world_import(client, headers, preview.json()["id"])
        assert task["status"] == "preview"
        assert seen["language"] == "en"
        assert task["result"]["language"] == "en"


def test_generated_fallback_prefers_three_kingdoms_seed_graph() -> None:
    candidates, relationships = _fallback_import_payload_v2("三国人物", 5, "zh")
    assert len(candidates) == 5
    assert all(item["id"].isascii() for item in candidates)
    assert relationships
    assert all(item["source_type"] == "generated_unverified" for item in candidates)
    assert all(not item.get("sources") for item in candidates)


def test_world_simulation_uses_model_payload_and_scenario_language(monkeypatch) -> None:
    def fake_run(self, *, world, people, relationships, scenario, rounds, completeness, source_coverage, disclaimer):
        return {
            "language": "zh",
            "fallback": False,
            "rounds": [
                {
                    "round": 1,
                    "summary": "刘备先亡使蜀汉继承秩序立刻承压。",
                    "turning_points": ["关羽北伐的政治支撑变弱"],
                    "uncertainties": ["诸葛亮是否能迅速稳定局势"],
                    "people": [
                        {
                            "persona_id": people[0].id,
                            "name": people[0].name,
                            "faction": people[0].faction,
                            "state": "震动",
                            "likely_action": "收拢旧部",
                            "possible_action": "收拢旧部",
                            "reasoning": "根据蜀汉阵营设定推演。",
                            "risk": "军心不稳",
                            "confidence": 0.66,
                            "setting_completeness": people[0].setting_completeness,
                            "simulated": True,
                        }
                    ],
                    "influences": [],
                    "mode": "role_sandbox",
                    "language": "zh",
                    "fallback": False,
                    "setting_completeness": completeness,
                    "source_coverage": source_coverage,
                    "disclaimer": disclaimer,
                }
            ],
        }

    monkeypatch.setattr(WorldAIService, "run_simulation", fake_run)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        persona = client.post(
            f"/api/worlds/{world_id}/personas",
            headers=headers,
            json={
                "name": "刘备",
                "summary": "蜀汉核心人物",
                "traits": ["仁厚"],
                "motivations": ["复兴汉室"],
                "faction": "蜀汉",
            },
        ).json()
        response = client.post(
            f"/api/worlds/{world_id}/simulations",
            headers=headers,
            json={
                "title": "刘备先亡",
                "scenario": "如果刘备死在关羽前面会怎样？",
                "participant_ids": [persona["id"]],
                "rounds": 1,
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["language"] == "zh"
        assert payload["fallback"] is False
        assert "刘备先亡" in payload["rounds"][0]["summary"]
        assert payload["rounds"][0]["people"][0]["likely_action"] == "收拢旧部"
