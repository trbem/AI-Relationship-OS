import logging
from typing import Any

from app.prompts.persona_prompt import PERSONA_SYSTEM_PROMPT
from app.services.ai_client import AIClient, AIClientError

logger = logging.getLogger(__name__)


def _build_persona_prompt(name: str, messages: list[str]) -> str:
    msg_block = "\n".join(f"- [{index + 1}] {message}" for index, message in enumerate(messages))
    return (
        f"联系人姓名：{name}\n"
        f"历史聊天记录：\n{msg_block}\n\n"
        "请基于以上证据输出该联系人的人物画像 JSON。"
    )


def _parse_persona_response(raw: dict[str, Any], name: str) -> dict[str, Any]:
    confidence = min(max(float(raw.get("confidence", 0.5)), 0.0), 1.0)
    return {
        "name": name,
        "traits": raw.get("traits") or [],
        "communication": raw.get("communication") or [],
        "interests": raw.get("interests") or [],
        "emotion_patterns": raw.get("emotion_patterns") or [],
        "keywords": raw.get("keywords") or [],
        "confidence": confidence,
        "evidence_note": raw.get(
            "evidence_note",
            "仅基于已有聊天样本做描述性归纳，不代表对真实人物的确定性判断。",
        ),
    }


def _fallback_persona(name: str, messages: list[str]) -> dict[str, Any]:
    sample = " ".join(messages[:20]).lower()
    traits: list[str] = []
    communication: list[str] = []
    interests: list[str] = []
    emotion_patterns: list[str] = []

    if any(word in sample for word in ["deadline", "progress", "result", "data", "进度", "结果", "数据"]):
        traits.append("结果导向")
        communication.append("偏好任务与结果表达")
    if any(word in sample for word in ["thanks", "sorry", "please", "谢谢", "抱歉", "请"]):
        emotion_patterns.append("礼貌表达较多")
    if any(len(message) < 30 for message in messages[:10]):
        communication.append("常用短句")

    if not traits:
        traits.append("画像样本不足，需要更多历史聊天")
    if not communication:
        communication.append("表达方式暂不稳定")
    if not emotion_patterns:
        emotion_patterns.append("情绪模式证据不足")
    if not interests:
        interests.append("兴趣线索不足")

    return {
        "name": name,
        "traits": traits,
        "communication": communication,
        "interests": interests,
        "emotion_patterns": emotion_patterns,
        "keywords": _top_keywords(messages),
        "confidence": 0.68 if len(messages) >= 5 else 0.42,
        "evidence_note": "仅基于已有聊天样本做描述性归纳，不代表对真实人物的确定性判断。",
    }


def _top_keywords(messages: list[str]) -> list[str]:
    words: dict[str, int] = {}
    for message in messages:
        for token in message.replace("，", " ").replace(",", " ").split():
            normalized = token.strip().lower()
            if len(normalized) < 2:
                continue
            words[normalized] = words.get(normalized, 0) + 1
    sorted_words = sorted(words.items(), key=lambda item: item[1], reverse=True)
    return [word for word, _count in sorted_words[:5]] or ["证据不足"]


class PersonaService:
    def __init__(self) -> None:
        self._client = AIClient()

    def generate_persona(self, name: str, messages: list[str]) -> dict[str, Any]:
        if not messages:
            return _fallback_persona(name, [])

        try:
            raw = self._client.chat_json(
                system_prompt=PERSONA_SYSTEM_PROMPT,
                user_prompt=_build_persona_prompt(name, messages),
                temperature=0.2,
            )
            return _parse_persona_response(raw, name)
        except (AIClientError, TypeError, ValueError) as exc:
            logger.warning("PersonaService falling back to rules: %s", exc)
            return _fallback_persona(name, messages)
