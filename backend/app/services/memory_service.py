from app.prompts.memory_prompt import MEMORY_SYSTEM_PROMPT
from app.services.ai_client import AIClient, AIClientError


class MemoryService:
    def extract_memories(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return []

        batch_text = "\n\n".join(
            f"[id:{item['id']}] {item.get('content', '')}" for item in messages
        )
        user_prompt = (
            "从以下聊天消息中提取 3-8 条关键记忆事件。\n"
            "每条记忆包含 event、emotion、importance(0.0-1.0) 和 "
            "source_message_ids(相关消息 ID 数组)。\n"
            '只输出 JSON 对象，格式为 {"memories": [...]}。\n\n'
            f"聊天消息：\n{batch_text}"
        )

        try:
            raw = AIClient().chat_json(
                system_prompt=MEMORY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
            )
            raw_memories = raw.get("memories", []) if isinstance(raw, dict) else []
            if isinstance(raw_memories, list):
                memories: list[dict] = []
                for item in raw_memories:
                    if not isinstance(item, dict):
                        continue
                    event = str(item.get("event", "")).strip()
                    if not event:
                        continue
                    importance = min(max(float(item.get("importance", 0.5)), 0.0), 1.0)
                    source_ids = item.get("source_message_ids", [])
                    if not isinstance(source_ids, list):
                        source_ids = [source_ids]
                    memories.append(
                        {
                            "event": event,
                            "emotion": str(item.get("emotion", "neutral")),
                            "importance": importance,
                            "source_message_ids": ",".join(map(str, source_ids)),
                            "timestamp": None,
                        }
                    )
                if memories:
                    return memories
        except (AIClientError, TypeError, ValueError):
            pass

        return self._fallback_extraction(messages)

    def _fallback_extraction(self, messages: list[dict]) -> list[dict]:
        event_keywords = {
            "conflict": ["argue", "conflict", "angry", "不满", "生气"],
            "collaboration": ["together", "plan", "合作", "一起"],
            "happy": ["great", "happy", "开心", "谢谢"],
            "apology": ["sorry", "抱歉", "道歉"],
            "request": ["please", "can you", "请求", "帮忙", "请"],
        }
        memories: list[dict] = []
        for item in messages:
            content = item["content"]
            lowered = content.lower()
            for label, keywords in event_keywords.items():
                if any(keyword in lowered for keyword in keywords):
                    memories.append(
                        {
                            "event": content[:120],
                            "emotion": self._emotion_for(label),
                            "importance": self._importance_for(label),
                            "source_message_ids": str(item.get("id", "")),
                            "timestamp": item.get("sent_at"),
                        }
                    )
                    break
        return memories

    @staticmethod
    def _emotion_for(label: str) -> str:
        return {
            "conflict": "negative",
            "collaboration": "positive",
            "happy": "positive",
            "apology": "mixed",
            "request": "neutral",
        }.get(label, "neutral")

    @staticmethod
    def _importance_for(label: str) -> float:
        return {
            "conflict": 0.9,
            "collaboration": 0.75,
            "happy": 0.6,
            "apology": 0.8,
            "request": 0.65,
        }.get(label, 0.5)
