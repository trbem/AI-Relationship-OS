from app.services import memory_service
from app.services.memory_service import MemoryService


class FakeAIClient:
    def chat_json(self, **_kwargs) -> dict:
        return {
            "memories": [
                {
                    "event": "Agreed to send the report",
                    "emotion": "positive",
                    "importance": 1.4,
                    "source_message_ids": ["m1", "m2"],
                }
            ]
        }


def test_extract_memories_reads_wrapped_array_and_clamps_importance(monkeypatch) -> None:
    monkeypatch.setattr(memory_service, "AIClient", FakeAIClient)

    result = MemoryService().extract_memories(
        [{"id": "m1", "content": "I will send the report", "sent_at": None}]
    )

    assert result == [
        {
            "event": "Agreed to send the report",
            "emotion": "positive",
            "importance": 1.0,
            "source_message_ids": "m1,m2",
            "timestamp": None,
        }
    ]


def test_fallback_extraction_supports_chinese_keywords(monkeypatch) -> None:
    class FailingAIClient:
        def chat_json(self, **_kwargs) -> dict:
            raise memory_service.AIClientError("unavailable")

    monkeypatch.setattr(memory_service, "AIClient", FailingAIClient)

    result = MemoryService().extract_memories(
        [{"id": "m1", "content": "请帮忙整理项目进度", "sent_at": None}]
    )

    assert result[0]["emotion"] == "neutral"
    assert result[0]["source_message_ids"] == "m1"
