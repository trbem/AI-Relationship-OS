from types import SimpleNamespace

import httpx
import pytest

from app.services.ai_client import AIClient, AIClientError


def make_client() -> AIClient:
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        completion_model="mimo-v2.5",
        llm_temperature=0.2,
        llm_base_url="https://example.test/v1",
        llm_api_key="test-key",
        llm_timeout_seconds=1.0,
        llm_provider="openai_compatible",
        llm_fallback_enabled=True,
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=1.0,
        ollama_model="local-model",
        embedding_model="local-hash-v1",
    )
    return client


def test_chat_json_parses_remote_json(monkeypatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client,
        "_post_openai_compatible",
        lambda _path, _payload, **_kwargs: {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        },
    )

    assert client.chat_json(system_prompt="system", user_prompt="user") == {
        "ok": True
    }


def test_authentication_failure_does_not_fallback(monkeypatch) -> None:
    client = make_client()
    fallback_called = False

    def fail_remote(**_kwargs):
        raise AIClientError("LLM request failed with status 401")

    def track_fallback(**_kwargs):
        nonlocal fallback_called
        fallback_called = True
        return {"ok": False}

    monkeypatch.setattr(client, "_chat_openai_json", fail_remote)
    monkeypatch.setattr(client, "_chat_ollama_json", track_fallback)

    with pytest.raises(AIClientError, match="status 401"):
        client.chat_json(system_prompt="system", user_prompt="user")
    assert fallback_called is False


def test_timeout_falls_back_to_ollama(monkeypatch) -> None:
    client = make_client()

    def fail_remote(**_kwargs):
        raise AIClientError("LLM request timed out")

    monkeypatch.setattr(client, "_chat_openai_json", fail_remote)
    monkeypatch.setattr(
        client,
        "_chat_ollama_json",
        lambda **_kwargs: {"source": "ollama"},
    )

    assert client.chat_json(system_prompt="system", user_prompt="user") == {
        "source": "ollama"
    }


def test_http_timeout_is_wrapped(monkeypatch) -> None:
    client = make_client()
    request = httpx.Request(
        "POST",
        "https://example.test/v1/chat/completions",
    )

    class TimeoutClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(httpx, "Client", TimeoutClient)

    with pytest.raises(AIClientError, match="timed out"):
        client._post_openai_compatible(
            "/chat/completions",
            {"model": "mimo-v2.5"},
        )


def test_connection_test_requires_strict_json(monkeypatch) -> None:
    client = make_client()

    def fake_post(**kwargs):
        assert kwargs["timeout_seconds"] == 12
        assert kwargs["payload"]["response_format"] == {"type": "json_object"}
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"status":"ok","capability":"json"}',
                    }
                }
            ]
        }

    monkeypatch.setattr(client, "_post_openai_json_with_config", fake_post)
    result = client.test_openai_compatible_connection(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="mimo-v2.5",
        timeout_seconds=12,
        temperature=0,
    )
    assert result["message"] == "strict JSON ok"


def test_chat_json_passes_timeout_override(monkeypatch) -> None:
    client = make_client()
    captured = {}

    def fake_post(_path, _payload, **kwargs):
        captured.update(kwargs)
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
        }

    monkeypatch.setattr(client, "_post_openai_compatible", fake_post)
    assert client.chat_json(
        system_prompt="system",
        user_prompt="user",
        timeout_seconds=120,
    ) == {"ok": True}
    assert captured["timeout_seconds"] == 120


def test_parse_json_content_reads_fenced_json() -> None:
    client = make_client()

    assert client._parse_json_content('```json\n{"ok": true}\n```') == {"ok": True}


def test_parse_json_content_reads_json_with_surrounding_text() -> None:
    client = make_client()

    assert client._parse_json_content('Sure:\n{"ok": true}\nDone.') == {"ok": True}


def test_parse_json_content_uses_first_balanced_object() -> None:
    client = make_client()

    assert client._parse_json_content('first {"ok": true} second {"ok": false}') == {
        "ok": True
    }


def test_parse_json_content_repairs_trailing_commas() -> None:
    client = make_client()

    assert client._parse_json_content('{"items": [1, 2,], "ok": true,}') == {
        "items": [1, 2],
        "ok": True,
    }


def test_parse_json_content_marks_invalid_json_response() -> None:
    client = make_client()

    with pytest.raises(AIClientError) as exc_info:
        client._parse_json_content('{"ok": true')

    assert exc_info.value.code == "INVALID_JSON_RESPONSE"
    assert "INVALID_JSON_RESPONSE" in str(exc_info.value)
