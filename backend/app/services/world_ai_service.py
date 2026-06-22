from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from app.models import PersonaWorld, WorldPersona, WorldRelationship
from app.services.ai_client import AIClient, AIClientError

logger = logging.getLogger(__name__)


ROLE_SANDBOX_NOTICE_ZH = "联网来源不可用，以下为模型基于通用知识生成的角色沙盘候选，未经过 Wikidata/Wikipedia 验证。"
ROLE_SANDBOX_NOTICE_EN = "Online sources are unavailable. The following role-sandbox candidates are model-generated and not verified by Wikidata/Wikipedia."


class WorldAIService:
    def generated_import_preview(
        self,
        query: str,
        limit: int,
        *,
        source_failures: list[dict] | None = None,
    ) -> dict:
        language = _detect_language(query)
        try:
            client = AIClient()
            raw = client.chat_json(
                system_prompt=_import_system_prompt(language),
                user_prompt=_import_user_prompt(query, limit, language),
                temperature=0.35,
                timeout_seconds=max(float(client.settings.llm_timeout_seconds), 60.0),
            )
            candidates, relationships = _normalize_import_payload(raw, limit)
        except (AIClientError, TypeError, ValueError) as exc:
            logger.warning("World import model fallback used: %s", exc)
            candidates, relationships = _fallback_import_payload_v2(query, limit, language)
        return {
            "query": query,
            "candidates": candidates,
            "relationships": relationships,
            "errors": ["Online sources unavailable; used model-generated role sandbox."],
            "source_failures": source_failures or [],
            "fallback_mode": "model_generated",
            "generated_notice": ROLE_SANDBOX_NOTICE_ZH if language == "zh" else ROLE_SANDBOX_NOTICE_EN,
            "language": language,
            "partial": True,
        }

    def run_simulation(
        self,
        *,
        world: PersonaWorld,
        people: list[WorldPersona],
        relationships: list[WorldRelationship],
        scenario: str,
        rounds: int,
        completeness: float,
        source_coverage: float,
        disclaimer: str,
    ) -> dict:
        language = _detect_language(scenario or world.name or "")
        context = _world_context(world, people, relationships)
        try:
            client = AIClient()
            # Role simulations ask for multi-round structured JSON, so the tiny
            # settings health check is not a realistic timeout budget.
            raw = client.chat_json(
                system_prompt=_simulation_system_prompt(language),
                user_prompt=_simulation_user_prompt(
                    scenario=scenario,
                    rounds=rounds,
                    context=context,
                    language=language,
                ),
                temperature=0.45,
                timeout_seconds=max(float(client.settings.llm_timeout_seconds), 120.0),
            )
            payload = _normalize_simulation_payload(
                raw,
                people,
                relationships,
                rounds,
                language,
                completeness,
                source_coverage,
                disclaimer,
                fallback=False,
            )
        except (AIClientError, TypeError, ValueError) as exc:
            logger.warning("World simulation model fallback used: %s", exc)
            payload = _fallback_simulation_payload_v2(
                people,
                relationships,
                scenario,
                rounds,
                language,
                completeness,
                source_coverage,
                disclaimer,
            )
        return payload


def _detect_language(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text or "") else "en"


def _import_system_prompt(language: str) -> str:
    response_language = "Chinese" if language == "zh" else "English"
    return (
        "You create fictional or historical role-sandbox character graphs. "
        "When online sources are unavailable, use broad public knowledge only, "
        "do not invent source URLs, and mark content as generated. "
        f"Return strict JSON in {response_language}."
    )


def _import_user_prompt(query: str, limit: int, language: str) -> str:
    return f"""
Topic: {query}
Maximum characters: {limit}

Return strict JSON:
{{
  "candidates": [
    {{
      "name": "character/person name",
      "aliases": ["optional alias"],
      "summary": "short setting summary",
      "faction": "camp/group",
      "traits": ["trait"],
      "motivations": ["goal"],
      "communication": ["style"]
    }}
  ],
  "relationships": [
    {{
      "source": "exact candidate name",
      "target": "exact candidate name",
      "type": "ally/enemy/family/subordinate/influence/cooperation",
      "directed": true,
      "strength": 0.7,
      "description": "why this relation matters"
    }}
  ]
}}

Use the user's language: {"Chinese" if language == "zh" else "English"}.
Keep the graph compact, representative, and suitable for a small desktop app.
""".strip()


def _normalize_import_payload(raw: dict[str, Any], limit: int) -> tuple[list[dict], list[dict]]:
    raw_candidates = raw.get("candidates", [])
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    candidates: list[dict] = []
    name_to_id: dict[str, str] = {}
    for index, value in enumerate(raw_candidates[:limit]):
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        if not name:
            continue
        candidate_id = f"generated:{_slug(name)}:{index}"
        name_to_id[name] = candidate_id
        candidates.append(
            {
                "id": candidate_id,
                "name": name,
                "aliases": _strings(value.get("aliases"))[:6],
                "summary": str(value.get("summary") or value.get("description") or name),
                "description": str(value.get("summary") or value.get("description") or ""),
                "source_type": "generated",
                "source_ref": candidate_id,
                "faction": str(value.get("faction") or ""),
                "traits": _strings(value.get("traits"))[:6],
                "motivations": _strings(value.get("motivations"))[:6],
                "communication": _strings(value.get("communication"))[:4],
                "sources": [
                    {
                        "source_type": "generated",
                        "external_id": candidate_id,
                        "url": "generated://role-sandbox",
                        "title": "AI generated role sandbox",
                    }
                ],
            }
        )
    raw_relationships = raw.get("relationships", [])
    if not isinstance(raw_relationships, list):
        raw_relationships = []
    relationships: list[dict] = []
    for value in raw_relationships[: limit * 3]:
        if not isinstance(value, dict):
            continue
        source = name_to_id.get(str(value.get("source") or "").strip())
        target = name_to_id.get(str(value.get("target") or "").strip())
        if not source or not target or source == target:
            continue
        relationships.append(
            {
                "source": source,
                "target": target,
                "type": str(value.get("type") or "influence")[:64],
                "directed": bool(value.get("directed", True)),
                "strength": _clamp_float(value.get("strength"), 0.6),
                "description": str(value.get("description") or ""),
                "confidence": 0.45,
                "source_type": "generated",
                "source_ref": "generated://role-sandbox",
            }
        )
    return candidates, relationships


def _fallback_import_payload(query: str, limit: int, language: str) -> tuple[list[dict], list[dict]]:
    if "三国" in query:
        names = ["刘备", "关羽", "张飞", "诸葛亮", "曹操", "孙权", "周瑜", "司马懿"]
        factions = ["蜀汉", "蜀汉", "蜀汉", "蜀汉", "曹魏", "东吴", "东吴", "曹魏"]
    else:
        names = [f"{query} 角色 {index + 1}" if language == "zh" else f"{query} Character {index + 1}" for index in range(min(limit, 6))]
        factions = ["核心阵营"] * len(names)
    candidates = []
    for index, name in enumerate(names[:limit]):
        candidate_id = f"generated:{_slug(name)}:{index}"
        candidates.append(
            {
                "id": candidate_id,
                "name": name,
                "aliases": [],
                "summary": f"{name} 的设定沙盘候选。" if language == "zh" else f"Model-generated role sandbox candidate for {name}.",
                "description": "",
                "source_type": "generated",
                "source_ref": candidate_id,
                "faction": factions[index] if index < len(factions) else "",
                "traits": [],
                "motivations": [],
                "communication": [],
                "sources": [
                    {
                        "source_type": "generated",
                        "external_id": candidate_id,
                        "url": "generated://role-sandbox",
                        "title": "AI generated role sandbox",
                    }
                ],
            }
        )
    relationships = []
    for index in range(max(0, len(candidates) - 1)):
        relationships.append(
            {
                "source": candidates[index]["id"],
                "target": candidates[index + 1]["id"],
                "type": "影响" if language == "zh" else "influence",
                "directed": True,
                "strength": 0.55,
                "description": "模型兜底生成的基础影响关系。" if language == "zh" else "Basic generated influence relation.",
                "confidence": 0.35,
                "source_type": "generated",
                "source_ref": "generated://role-sandbox",
            }
        )
    return candidates, relationships


def _fallback_import_payload_v2(query: str, limit: int, language: str) -> tuple[list[dict], list[dict]]:
    if _is_three_kingdoms_topic(query):
        seeds = [
            ("刘备", "蜀汉", "以复兴汉室为号召的政治领袖。", ["仁厚", "坚韧"], ["建立基业", "延续汉统"]),
            ("关羽", "蜀汉", "重义气、威望极高的核心将领。", ["忠义", "骄傲"], ["守护兄弟情义", "维护蜀汉声望"]),
            ("张飞", "蜀汉", "勇猛直接、情绪外露的猛将。", ["勇猛", "急躁"], ["保护刘备集团", "证明武勇"]),
            ("诸葛亮", "蜀汉", "擅长谋划、治理和稳定政权的军师。", ["谨慎", "克制"], ["稳定政权", "完成托付"]),
            ("曹操", "曹魏", "雄才多疑、善于用人与把握局势的枭雄。", ["果断", "多疑"], ["统一天下", "掌控主动权"]),
            ("孙权", "东吴", "善于平衡联盟、臣属和江东利益的统治者。", ["务实", "权衡"], ["守住江东", "扩张利益"]),
            ("周瑜", "东吴", "才华出众、维护江东利益的统帅。", ["敏锐", "骄傲"], ["击败强敌", "巩固江东"]),
            ("司马懿", "曹魏", "隐忍谨慎、擅长长期布局的权臣。", ["隐忍", "审慎"], ["保存实力", "等待时机"]),
        ][:limit]
        candidates = [_candidate_from_seed(index, *seed) for index, seed in enumerate(seeds)]
        by_name = {item["name"]: item["id"] for item in candidates}
        relation_seeds = [
            ("刘备", "关羽", "结义", 0.95, "桃园结义形成的强信任纽带。"),
            ("刘备", "张飞", "结义", 0.92, "共同创业与兄弟情义支撑联盟。"),
            ("刘备", "诸葛亮", "君臣", 0.95, "三顾茅庐后形成高度信任。"),
            ("曹操", "刘备", "敌对", 0.9, "争夺天下的主要对手。"),
            ("刘备", "孙权", "联盟", 0.65, "阶段性联合对抗曹操，但利益并不完全一致。"),
            ("孙权", "周瑜", "君臣", 0.9, "共同维护江东利益。"),
            ("周瑜", "诸葛亮", "竞争", 0.75, "小说叙事中存在突出的智谋竞争。"),
            ("司马懿", "曹操", "上下级", 0.6, "司马氏在曹魏体系内逐步积累影响。"),
        ]
        relationships = [
            {
                "source": by_name[source],
                "target": by_name[target],
                "type": rel_type,
                "directed": True,
                "strength": strength,
                "description": description,
                "confidence": 0.45,
                "source_type": "generated",
                "source_ref": "generated://role-sandbox",
            }
            for source, target, rel_type, strength, description in relation_seeds
            if source in by_name and target in by_name
        ]
        return candidates, relationships

    if language == "zh":
        names = [f"{query} 角色 {index + 1}" for index in range(min(limit, 6))]
        factions = ["核心阵营"] * len(names)
    else:
        names = [f"{query} Character {index + 1}" for index in range(min(limit, 6))]
        factions = ["Core faction"] * len(names)
    candidates = [
        _candidate_from_seed(
            index,
            name,
            factions[index] if index < len(factions) else "",
            f"{name} 的设定沙盘候选。" if language == "zh" else f"Model-generated role sandbox candidate for {name}.",
            [],
            [],
        )
        for index, name in enumerate(names[:limit])
    ]
    relationships = [
        {
            "source": candidates[index]["id"],
            "target": candidates[index + 1]["id"],
            "type": "影响" if language == "zh" else "influence",
            "directed": True,
            "strength": 0.55,
            "description": "模型兜底生成的基础影响关系。" if language == "zh" else "Basic generated influence relation.",
            "confidence": 0.35,
            "source_type": "generated",
            "source_ref": "generated://role-sandbox",
        }
        for index in range(max(0, len(candidates) - 1))
    ]
    return candidates, relationships


def _is_three_kingdoms_topic(query: str) -> bool:
    normalized = (query or "").casefold()
    return any(
        marker in normalized
        for marker in ["三国", "三國", "刘备", "劉備", "曹操", "蜀汉", "蜀漢", "three kingdoms"]
    )


def _candidate_from_seed(
    index: int,
    name: str,
    faction: str,
    summary: str,
    traits: list[str],
    motivations: list[str],
) -> dict:
    candidate_id = f"generated:{_slug(name)}:{index}"
    return {
        "id": candidate_id,
        "name": name,
        "aliases": [],
        "summary": summary,
        "description": summary,
        "source_type": "generated",
        "source_ref": candidate_id,
        "faction": faction,
        "traits": traits,
        "motivations": motivations,
        "communication": [],
        "sources": [
            {
                "source_type": "generated",
                "external_id": candidate_id,
                "url": "generated://role-sandbox",
                "title": "AI generated role sandbox",
            }
        ],
    }


def _simulation_system_prompt(language: str) -> str:
    response_language = "Chinese" if language == "zh" else "English"
    return (
        "You are a careful role-sandbox simulation engine. Use the provided world "
        "setting, characters, factions, relationships, and the user's counterfactual "
        "scenario. Separate historical/setting facts from simulated outcomes. "
        "Never claim certainty. Return strict JSON only. "
        f"Write all user-facing text in {response_language}."
    )


def _simulation_user_prompt(*, scenario: str, rounds: int, context: dict, language: str) -> str:
    return f"""
Scenario: {scenario}
Rounds: {rounds}
World context JSON: {json.dumps(context, ensure_ascii=False)}

Return strict JSON:
{{
  "rounds": [
    {{
      "round": 1,
      "summary": "situation summary",
      "turning_points": ["key change"],
      "uncertainties": ["what remains uncertain"],
      "people": [
        {{
          "persona_id": "id from context",
          "name": "name",
          "state": "current mental/political state",
          "likely_action": "likely action",
          "reasoning": "setting-based reason",
          "risk": "risk",
          "confidence": 0.6
        }}
      ],
      "influences": [
        {{
          "source": "persona id",
          "target": "persona id",
          "type": "influence type",
          "strength": 0.6,
          "description": "why influence matters"
        }}
      ]
    }}
  ]
}}
Language: {"Chinese" if language == "zh" else "English"}.
""".strip()


def _world_context(
    world: PersonaWorld,
    people: list[WorldPersona],
    relationships: list[WorldRelationship],
) -> dict:
    return {
        "world": {
            "name": world.name,
            "theme": world.theme,
            "type": world.world_type,
            "background": world.world_background or world.description,
            "source_type": world.source_type,
            "version": world.version,
        },
        "people": [
            {
                "id": item.id,
                "name": item.name,
                "aliases": _loads(item.aliases_json, []),
                "summary": item.summary,
                "traits": _loads(item.traits_json, []),
                "motivations": _loads(item.motivations_json, []),
                "values": _loads(item.values_json, []),
                "abilities": _loads(item.abilities_json, []),
                "communication": _loads(item.communication_json, []),
                "faction": item.faction,
                "background": item.background,
                "source_type": item.source_type,
            }
            for item in people
        ],
        "relationships": [
            {
                "source": item.source_persona_id,
                "target": item.target_persona_id,
                "type": item.relationship_type,
                "directed": item.directed,
                "strength": item.strength,
                "description": item.description,
                "source_type": item.source_type,
            }
            for item in relationships
        ],
    }


def _normalize_simulation_payload(
    raw: dict[str, Any],
    people: list[WorldPersona],
    relationships: list[WorldRelationship],
    rounds: int,
    language: str,
    completeness: float,
    source_coverage: float,
    disclaimer: str,
    *,
    fallback: bool,
) -> dict:
    known_ids = {item.id for item in people}
    raw_rounds = raw.get("rounds", [])
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise ValueError("missing rounds")
    normalized = []
    for index, value in enumerate(raw_rounds[:rounds], start=1):
        if not isinstance(value, dict):
            continue
        people_states = []
        for raw_person in value.get("people", []):
            if not isinstance(raw_person, dict):
                continue
            persona_id = str(raw_person.get("persona_id") or "")
            if persona_id not in known_ids:
                name = str(raw_person.get("name") or "")
                match = next((item for item in people if item.name == name), None)
                persona_id = match.id if match else ""
            if not persona_id:
                continue
            person = next(item for item in people if item.id == persona_id)
            people_states.append(
                {
                    "persona_id": persona_id,
                    "name": person.name,
                    "faction": person.faction,
                    "state": str(raw_person.get("state") or ""),
                    "likely_action": str(raw_person.get("likely_action") or raw_person.get("possible_action") or ""),
                    "possible_action": str(raw_person.get("likely_action") or raw_person.get("possible_action") or ""),
                    "reasoning": str(raw_person.get("reasoning") or ""),
                    "risk": str(raw_person.get("risk") or ""),
                    "confidence": _clamp_float(raw_person.get("confidence"), 0.5),
                    "setting_completeness": person.setting_completeness,
                    "simulated": True,
                }
            )
        if not people_states:
            raise ValueError("round missing people")
        normalized.append(
            {
                "round": int(value.get("round") or index),
                "summary": str(value.get("summary") or ""),
                "turning_points": _strings(value.get("turning_points"))[:6],
                "uncertainties": _strings(value.get("uncertainties"))[:6],
                "people": people_states,
                "influences": _normalize_influences(value.get("influences"), relationships),
                "mode": "role_sandbox",
                "language": language,
                "fallback": fallback,
                "setting_completeness": completeness,
                "source_coverage": source_coverage,
                "disclaimer": disclaimer,
            }
        )
    if not normalized:
        raise ValueError("no normalized rounds")
    return {"language": language, "fallback": fallback, "rounds": normalized}


def _fallback_simulation_payload(
    people: list[WorldPersona],
    relationships: list[WorldRelationship],
    scenario: str,
    rounds: int,
    language: str,
    completeness: float,
    source_coverage: float,
    disclaimer: str,
) -> dict:
    output = []
    for round_number in range(1, rounds + 1):
        people_states = []
        for item in people:
            traits = _loads(item.traits_json, [])
            state = traits[(round_number - 1) % len(traits)] if traits else (
                "根据当前设定观察局势" if language == "zh" else "Observes the situation through current setting"
            )
            action = (
                f"围绕“{scenario[:80]}”按其阵营、动机和关系作出回应"
                if language == "zh"
                else f"Responds to '{scenario[:80]}' according to faction, motives, and relationships"
            )
            people_states.append(
                {
                    "persona_id": item.id,
                    "name": item.name,
                    "faction": item.faction,
                    "state": state,
                    "likely_action": action,
                    "possible_action": action,
                    "reasoning": "模型不可用，使用人物设定和关系进行规则降级。" if language == "zh" else "Model unavailable; rule fallback used character settings and relationships.",
                    "risk": "不确定性较高" if language == "zh" else "High uncertainty",
                    "confidence": 0.35,
                    "setting_completeness": item.setting_completeness,
                    "simulated": True,
                }
            )
        output.append(
            {
                "round": round_number,
                "summary": (
                    f"第 {round_number} 轮：局势围绕用户假设继续发散。"
                    if language == "zh"
                    else f"Round {round_number}: the situation continues to branch from the user's premise."
                ),
                "turning_points": [],
                "uncertainties": ["模型不可用，结论只作为设定沙盘。"] if language == "zh" else ["Model unavailable; result is a setting sandbox only."],
                "people": people_states,
                "influences": _normalize_influences([], relationships),
                "mode": "role_sandbox",
                "language": language,
                "fallback": True,
                "setting_completeness": completeness,
                "source_coverage": source_coverage,
                "disclaimer": disclaimer,
            }
        )
    return {"language": language, "fallback": True, "rounds": output}


def _fallback_simulation_payload_v2(
    people: list[WorldPersona],
    relationships: list[WorldRelationship],
    scenario: str,
    rounds: int,
    language: str,
    completeness: float,
    source_coverage: float,
    disclaimer: str,
) -> dict:
    relation_notes = _relationship_notes(relationships)
    output = []
    for round_number in range(1, rounds + 1):
        people_states = []
        for index, item in enumerate(people):
            traits = _loads(item.traits_json, [])
            motivations = _loads(item.motivations_json, [])
            state = traits[(round_number - 1) % len(traits)] if traits else (
                "观察局势" if language == "zh" else "Observing the situation"
            )
            motive = motivations[0] if motivations else (
                "维护自身阵营" if language == "zh" else "protecting faction interests"
            )
            relation_note = relation_notes.get(item.id, "")
            if language == "zh":
                action = _zh_fallback_action(item, scenario, round_number, motive, relation_note, index)
                reasoning = f"基于人物设定、阵营目标“{motive}”以及既有关联关系进行规则降级推演。"
                if relation_note:
                    reasoning += f" 关键关系：{relation_note}"
                risk = "模型不可用，具体结局不确定性较高。"
            else:
                action = _en_fallback_action(item, scenario, round_number, motive, relation_note, index)
                reasoning = f"Rule fallback used the character setting, faction motive '{motive}', and known relationships."
                if relation_note:
                    reasoning += f" Key relation: {relation_note}"
                risk = "Model unavailable, so the concrete outcome is highly uncertain."
            people_states.append(
                {
                    "persona_id": item.id,
                    "name": item.name,
                    "faction": item.faction,
                    "state": state,
                    "likely_action": action,
                    "possible_action": action,
                    "reasoning": reasoning,
                    "risk": risk,
                    "confidence": 0.35,
                    "setting_completeness": item.setting_completeness,
                    "simulated": True,
                }
            )
        output.append(
            {
                "round": round_number,
                "summary": (
                    f"第 {round_number} 轮：围绕“{scenario[:48]}”展开保守沙盘，重点观察阵营稳定、联盟裂变和权力真空。"
                    if language == "zh"
                    else f"Round {round_number}: conservative sandbox around '{scenario[:48]}', watching faction stability, alliance shifts, and power vacuum."
                ),
                "turning_points": _fallback_turning_points(language, round_number),
                "uncertainties": (
                    ["模型服务不可用，本轮只根据人物设定与基础关系进行规则降级。"]
                    if language == "zh"
                    else ["Model unavailable; this round is a rule fallback based on settings and relationships."]
                ),
                "people": people_states,
                "influences": _normalize_influences([], relationships),
                "mode": "role_sandbox",
                "language": language,
                "fallback": True,
                "setting_completeness": completeness,
                "source_coverage": source_coverage,
                "disclaimer": disclaimer,
            }
        )
    return {"language": language, "fallback": True, "rounds": output}


def _relationship_notes(relationships: list[WorldRelationship]) -> dict[str, str]:
    notes: dict[str, list[str]] = {}
    for rel in relationships[:16]:
        text = f"{rel.relationship_type} {rel.description or ''}".strip()
        if not text:
            continue
        notes.setdefault(rel.source_persona_id, []).append(text)
        notes.setdefault(rel.target_persona_id, []).append(text)
    return {key: "；".join(value[:2]) for key, value in notes.items()}


def _zh_fallback_action(
    item: WorldPersona,
    scenario: str,
    round_number: int,
    motive: str,
    relation_note: str,
    index: int,
) -> str:
    faction = item.faction or "自身阵营"
    if round_number == 1:
        return f"先稳定{faction}内部预期，围绕“{scenario[:36]}”判断继承、军心和盟友反应。"
    if index % 3 == 0:
        return f"尝试把局势解释为有利于{faction}的机会，并以“{motive}”为目标争取主动。"
    if index % 3 == 1:
        return f"保持观望并测试盟友立场，避免在信息不足时过早摊牌。"
    if relation_note:
        return f"利用既有关联关系施压或斡旋，优先降低{faction}的连锁风险。"
    return f"调整资源和话语，等待下一轮局势更清晰后再行动。"


def _en_fallback_action(
    item: WorldPersona,
    scenario: str,
    round_number: int,
    motive: str,
    relation_note: str,
    index: int,
) -> str:
    faction = item.faction or "their faction"
    if round_number == 1:
        return f"Stabilizes expectations inside {faction} and reads succession, morale, and ally responses around '{scenario[:36]}'."
    if index % 3 == 0:
        return f"Frames the disruption as an opportunity for {faction}, pursuing '{motive}' before rivals settle."
    if index % 3 == 1:
        return "Waits and tests ally positions, avoiding an early commitment while information is thin."
    if relation_note:
        return f"Uses existing relationships to pressure or mediate, trying to reduce cascading risk for {faction}."
    return "Rebalances resources and messaging while waiting for the next signal."


def _fallback_turning_points(language: str, round_number: int) -> list[str]:
    if language == "zh":
        return [
            "权力真空会先影响阵营内部稳定。",
            "盟友会重新计算承诺与收益。",
        ] if round_number == 1 else [
            "外部对手可能试探边界。",
            "继承与军心问题会放大既有矛盾。",
        ]
    return [
        "The power vacuum first affects internal faction stability.",
        "Allies recalculate commitments and gains.",
    ] if round_number == 1 else [
        "External rivals may probe boundaries.",
        "Succession and morale amplify existing tensions.",
    ]


def _normalize_influences(value: Any, relationships: list[WorldRelationship]) -> list[dict]:
    if not isinstance(value, list):
        value = []
    influences = []
    for item in value[:24]:
        if not isinstance(item, dict):
            continue
        influences.append(
            {
                "source": str(item.get("source") or ""),
                "target": str(item.get("target") or ""),
                "type": str(item.get("type") or "influence"),
                "strength": _clamp_float(item.get("strength"), 0.5),
                "description": str(item.get("description") or ""),
                "simulated": True,
            }
        )
    if influences:
        return influences
    return [
        {
            "source": rel.source_persona_id,
            "target": rel.target_persona_id,
            "type": rel.relationship_type,
            "strength": rel.strength,
            "description": rel.description or "",
            "simulated": True,
        }
        for rel in relationships
    ]


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _clamp_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(0.0, min(1.0, number)), 3)


def _slug(value: str) -> str:
    cleaned = re.sub(r"\s+", "-", value.strip().lower())
    cleaned = re.sub(r"[^0-9a-zA-Z_-]+", "", cleaned)
    if cleaned:
        return cleaned[:48]
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"g-{digest}"
