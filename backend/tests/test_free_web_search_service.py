import pytest

from app.services.ai_client import AIClient, AIClientError
from app.services.free_web_search_service import (
    FreeWebWorldSearchService,
    WebSource,
    _search_queries,
)
from app.services.openai_web_search_service import WorldImportError


def _source() -> WebSource:
    return WebSource(
        title="Example World characters",
        url="https://example.test/world/characters",
        snippet="Alice and Bob are listed as characters.",
        excerpt="Alice is a leader. Bob is an ally.",
    )


def test_free_web_extracts_source_verified_candidates(monkeypatch) -> None:
    def collect(self, query: str, language: str = "zh"):
        assert language == "zh"
        return [_source()], []

    def chat_json(self, **kwargs):
        assert "https://example.test/world/characters" in kwargs["user_prompt"]
        assert "Target output language: Simplified Chinese" in kwargs["user_prompt"]
        return {
            "work": {"title": "Example World", "author": "Anon"},
            "candidates": [
                {
                    "id": "alice",
                    "name": "Alice",
                    "summary": "A source-backed leader.",
                    "confidence": 0.8,
                    "sources": [
                        {
                            "title": "Example World characters",
                            "url": "https://example.test/world/characters",
                        }
                    ],
                }
            ],
            "relationships": [],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    result = FreeWebWorldSearchService().search_world("Example World", 50)

    assert result["provider"] == "free_web"
    assert result["source_type"] == "free_web"
    assert result["candidates"][0]["name"] == "Alice"
    assert result["candidates"][0]["verification_status"] == "web_verified"
    assert result["candidates"][0]["source_type"] == "free_web"


def test_free_web_no_relevant_work_when_search_has_no_sources(monkeypatch) -> None:
    def collect(self, query: str, language: str = "zh"):
        return [], []

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)

    with pytest.raises(WorldImportError) as exc_info:
        FreeWebWorldSearchService().search_world("Missing Work", 10)

    assert exc_info.value.detail.code == "NO_RELEVANT_WORK"


def test_free_web_no_character_information_when_extraction_has_no_candidates(
    monkeypatch,
) -> None:
    def collect(self, query: str, language: str = "zh"):
        return [_source()], []

    def chat_json(self, **kwargs):
        return {
            "work": {"title": "Example World"},
            "candidates": [],
            "relationships": [],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    with pytest.raises(WorldImportError) as exc_info:
        FreeWebWorldSearchService().search_world("Example World", 10)

    assert exc_info.value.detail.code == "NO_CHARACTER_INFORMATION"


def test_free_web_partial_source_failures_do_not_block_candidates(monkeypatch) -> None:
    def collect(self, query: str, language: str = "zh"):
        return [_source()], [{"source": "duckduckgo", "stage": "searching"}]

    def chat_json(self, **kwargs):
        return {
            "work": {"title": "Example World"},
            "candidates": [
                {
                    "id": "alice",
                    "name": "Alice",
                    "summary": "A source-backed leader.",
                    "sources": [
                        {
                            "title": "Example World characters",
                            "url": "https://example.test/world/characters",
                        }
                    ],
                }
            ],
            "relationships": [],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    result = FreeWebWorldSearchService().search_world("Example World", 10)

    assert result["partial"] is True
    assert result["source_failures"][0]["source"] == "duckduckgo"


def test_free_web_extraction_failure_is_structured(monkeypatch) -> None:
    def collect(self, query: str, language: str = "zh"):
        return [_source()], []

    def chat_json(self, **kwargs):
        raise AIClientError("model unavailable")

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    with pytest.raises(WorldImportError) as exc_info:
        FreeWebWorldSearchService().search_world("Example World", 10)

    assert exc_info.value.detail.code == "EXTRACTION_FAILED"


def test_free_web_auto_language_resolves_from_query(monkeypatch) -> None:
    seen_languages: list[str] = []

    def collect(self, query: str, language: str = "zh"):
        seen_languages.append(language)
        return [_source()], []

    def chat_json(self, **kwargs):
        return {
            "work": {"title": "Example World"},
            "candidates": [
                {
                    "id": "alice",
                    "name": "Alice",
                    "summary": "A source-backed leader.",
                    "sources": [
                        {
                            "title": "Example World characters",
                            "url": "https://example.test/world/characters",
                        }
                    ],
                }
            ],
            "relationships": [],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    FreeWebWorldSearchService().search_world("三国演义", 10, language="auto")
    FreeWebWorldSearchService().search_world("Greek mythology", 10, language="auto")

    assert seen_languages == ["zh", "en"]


def test_search_queries_use_language_suffixes() -> None:
    zh_queries = _search_queries("三国演义", "zh")
    en_queries = _search_queries("Greek mythology", "en")

    assert "三国演义 人物" in zh_queries
    assert "三国演义 角色" in zh_queries
    assert all("浜虹墿" not in item for item in zh_queries)
    assert "Greek mythology characters" in en_queries
    assert "Greek mythology cast" in en_queries


def test_free_web_single_disambiguation_auto_preview(monkeypatch) -> None:
    def collect(self, query: str, language: str = "zh"):
        return [_source()], []

    def chat_json(self, **kwargs):
        return {
            "work": {"title": "Example World"},
            "disambiguation_options": [
                {
                    "id": "example-novel",
                    "title": "Example World",
                    "medium": "novel",
                    "reason": "Only one strong match.",
                    "sources": [
                        {
                            "title": "Example World characters",
                            "url": "https://example.test/world/characters",
                        }
                    ],
                }
            ],
            "candidates": [
                {
                    "id": "alice",
                    "name": "Alice",
                    "summary": "A source-backed leader.",
                    "sources": [
                        {
                            "title": "Example World characters",
                            "url": "https://example.test/world/characters",
                        }
                    ],
                }
            ],
            "relationships": [],
        }

    monkeypatch.setattr(FreeWebWorldSearchService, "_collect_sources", collect)
    monkeypatch.setattr(AIClient, "chat_json", chat_json)

    result = FreeWebWorldSearchService().search_world("Example World", 10)

    assert "status_hint" not in result
    assert result["disambiguation_options"] == []
    assert result["selected_disambiguation"]["id"] == "example-novel"
