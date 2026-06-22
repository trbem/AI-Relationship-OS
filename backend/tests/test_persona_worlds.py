import time

from fastapi.testclient import TestClient

from app.main import app
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


def test_manual_world_graph_simulation_and_export() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        ids = []
        for name, faction in (("甲", "A"), ("乙", "B")):
            response = client.post(
                f"/api/worlds/{world_id}/personas",
                headers=headers,
                json={
                    "name": name,
                    "summary": f"{name}的人物简介",
                    "traits": ["谨慎"],
                    "motivations": ["完成目标"],
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
                "relationship_type": "合作",
                "strength": 0.8,
            },
        )
        assert relationship.status_code == 201

        graph = client.get(f"/api/worlds/{world_id}/graph", headers=headers)
        assert graph.status_code == 200
        assert len(graph.json()["nodes"]) == 2
        assert all(node["type"] == "persona" for node in graph.json()["nodes"])
        assert not any(node["name"] == "我" for node in graph.json()["nodes"])

        simulation = client.post(
            f"/api/worlds/{world_id}/simulations",
            headers=headers,
            json={
                "title": "谈判",
                "scenario": "两人需要决定是否合作。",
                "participant_ids": ids,
                "rounds": 5,
            },
        )
        assert simulation.status_code == 201
        result = simulation.json()
        assert result["mode"] == "role_sandbox"
        assert len(result["rounds"]) == 5
        assert "证据" not in str(result)
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
        assert promoted.json()["label"] == "虚构衍生内容"

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

        romance_id = _world(client, headers, "演义")
        history_id = _world(client, headers, "历史")
        water_margin_id = _world(client, headers, "水浒")
        journey_id = _world(client, headers, "西游")
        red_chamber_id = _world(client, headers, "红楼")
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
        assert "貂蝉" not in history_names
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
    def fake_search(self, query: str, limit: int) -> dict:
        return {
            "query": query,
            "partial": True,
            "errors": ["第二来源暂不可用"],
            "relationships": [],
            "candidates": [
                {
                    "id": "Q123",
                    "name": "示例人物",
                    "summary": "来自来源的摘要。",
                    "aliases": ["样例"],
                    "sources": [
                        {
                            "source_type": "wikidata",
                            "external_id": "Q123",
                            "url": "https://www.wikidata.org/wiki/Q123",
                            "title": "示例人物",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(WorldImportService, "search", fake_search)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "示例", "limit": 20},
        )
        assert preview.status_code == 201
        assert preview.json()["status"] == "partial"
        task_id = preview.json()["id"]
        for expected in (1, 0):
            confirmed = client.post(
                f"/api/world-imports/{task_id}/confirm",
                headers=headers,
                json={"world_id": world_id, "candidate_ids": ["Q123"]},
            )
            assert confirmed.status_code == 200
            assert confirmed.json()["imported_personas"] == expected
        detail = client.get(f"/api/worlds/{world_id}", headers=headers).json()
        assert detail["persona_count"] == 1
        assert detail["personas"][0]["source_type"] == "wikidata"


def test_online_preview_uses_generated_fallback_and_imports_relationships(monkeypatch) -> None:
    def empty_search(self, query: str, limit: int) -> dict:
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
                    "source_type": "generated",
                    "faction": "蜀汉",
                    "traits": ["仁厚"],
                    "motivations": ["复兴汉室"],
                    "sources": [
                        {
                            "source_type": "generated",
                            "external_id": "generated:liu-bei",
                            "url": "generated://role-sandbox",
                            "title": "AI generated role sandbox",
                        }
                    ],
                },
                {
                    "id": "generated:guan-yu",
                    "name": "关羽",
                    "summary": "刘备重要盟友",
                    "source_type": "generated",
                    "faction": "蜀汉",
                    "sources": [
                        {
                            "source_type": "generated",
                            "external_id": "generated:guan-yu",
                            "url": "generated://role-sandbox",
                            "title": "AI generated role sandbox",
                        }
                    ],
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
                    "source_type": "generated",
                    "source_ref": "generated://role-sandbox",
                }
            ],
        }

    monkeypatch.setattr(WorldImportService, "search", empty_search)
    monkeypatch.setattr(WorldAIService, "generated_import_preview", generated)
    with TestClient(app) as client:
        headers = _register(client)
        world_id = _world(client, headers)
        preview = client.post(
            "/api/world-imports/search",
            headers=headers,
            json={"query": "三国人物", "limit": 20},
        )
        assert preview.status_code == 201
        result = preview.json()["result"]
        assert result["fallback_mode"] == "model_generated"
        confirmed = client.post(
            f"/api/world-imports/{preview.json()['id']}/confirm",
            headers=headers,
            json={
                "world_id": world_id,
                "candidate_ids": ["generated:liu-bei", "generated:guan-yu"],
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["imported_relationships"] == 1
        detail = client.get(f"/api/worlds/{world_id}", headers=headers).json()
        assert {item["source_type"] for item in detail["personas"]} == {"generated"}
        assert detail["relationship_count"] == 1


def test_generated_fallback_prefers_three_kingdoms_seed_graph() -> None:
    candidates, relationships = _fallback_import_payload_v2("三国人物", 5, "zh")
    names = {item["name"] for item in candidates}
    assert {"刘备", "关羽", "曹操"} <= names
    assert all(item["id"].isascii() for item in candidates)
    assert relationships
    assert any(item["type"] == "结义" for item in relationships)


def test_world_simulation_uses_model_payload_and_scenario_language(monkeypatch) -> None:
    def fake_run(self, *, world, people, relationships, scenario, rounds, completeness, source_coverage, disclaimer):
        return {
            "language": "zh",
            "fallback": False,
            "rounds": [
                {
                    "round": 1,
                    "summary": "刘备先亡使蜀汉继承秩序立刻承压。",
                    "turning_points": ["关羽北伐的政治支撑削弱"],
                    "uncertainties": ["诸葛亮是否能迅速稳定局势"],
                    "people": [
                        {
                            "persona_id": people[0].id,
                            "name": people[0].name,
                            "faction": people[0].faction,
                            "state": "震动",
                            "likely_action": "收拢旧部",
                            "possible_action": "收拢旧部",
                            "reasoning": "根据蜀汉阵营设定推演",
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
