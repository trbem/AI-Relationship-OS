import httpx
import pytest

from app.services.openai_web_search_service import (
    OpenAIWebSearchService,
    WorldImportError,
    _normalize_responses_base_url,
)


def test_normalizes_openai_root_to_v1() -> None:
    assert _normalize_responses_base_url("https://api.openai.com") == "https://api.openai.com/v1"
    assert _normalize_responses_base_url("https://api.openai.com/") == "https://api.openai.com/v1"


def test_normalizes_existing_v1_without_duplication() -> None:
    assert _normalize_responses_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert _normalize_responses_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"


def test_normalizes_full_responses_endpoint_to_base_url() -> None:
    assert (
        _normalize_responses_base_url("https://api.openai.com/v1/responses")
        == "https://api.openai.com/v1"
    )


def test_empty_404_is_reported_as_web_search_unsupported(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class DummyClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict, json: dict) -> httpx.Response:
            captured["url"] = url
            request = httpx.Request("POST", url)
            return httpx.Response(404, request=request, text="")

    monkeypatch.setattr(httpx, "Client", DummyClient)

    service = OpenAIWebSearchService()
    with pytest.raises(WorldImportError) as exc_info:
        service.test_connection(
            api_key="test-key",
            base_url="https://api.openai.com",
            model="test-model",
            timeout_seconds=10,
        )

    detail = exc_info.value.detail
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert detail.code == "WEB_SEARCH_UNSUPPORTED"
    assert detail.retryable is False
    assert "POST https://api.openai.com/v1/responses returned HTTP 404" in detail.technical_summary


def test_connection_error_stays_network_unavailable(monkeypatch) -> None:
    class DummyClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict, json: dict) -> httpx.Response:
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(httpx, "Client", DummyClient)

    service = OpenAIWebSearchService()
    with pytest.raises(WorldImportError) as exc_info:
        service.test_connection(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="test-model",
            timeout_seconds=10,
        )

    detail = exc_info.value.detail
    assert detail.code == "NETWORK_UNAVAILABLE"
    assert detail.retryable is True
    assert "POST https://api.openai.com/v1/responses failed: ConnectError" in detail.technical_summary
