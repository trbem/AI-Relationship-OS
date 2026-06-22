import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class AIClientError(RuntimeError):
    pass


class AIClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        provider = getattr(self.settings, "llm_provider", "openai_compatible").lower()
        remote_configured = bool(self.settings.llm_base_url and self.settings.llm_api_key)
        if provider == "ollama" or not remote_configured:
            try:
                return self._chat_ollama_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=self.settings.ollama_model,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                )
            except AIClientError as exc:
                if not remote_configured:
                    raise
                if not self._should_try_ollama(exc):
                    raise
                logger.warning("Ollama failed, trying OpenAI-compatible provider: %s", exc)

        try:
            return self._chat_openai_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model
                or getattr(self.settings, "llm_model", None)
                or self.settings.completion_model,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
            )
        except AIClientError as exc:
            if not self._should_try_ollama(exc):
                raise
            logger.warning("Remote LLM failed, trying Ollama fallback: %s", exc)

        return self._chat_ollama_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.settings.ollama_model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

    def build_embedding_ref(self, *, text: str, model: str | None = None) -> str:
        text_preview = text.strip().replace("\n", " ")[:48] or "empty"
        prompt = (
            "Return a short JSON object describing this text for retrieval metadata. "
            'Use keys summary and keywords. Text: ' + text[:4000]
        )
        payload = self.chat_json(
            system_prompt="You produce compact retrieval metadata as strict JSON.",
            user_prompt=prompt,
            model=model or self.settings.embedding_model,
            temperature=0,
        )
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return f"llmref:{model or self.settings.embedding_model}:{text_preview}:{compact[:200]}"

    def test_openai_compatible_connection(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        if not base_url:
            raise AIClientError("OpenAI-compatible base URL is not configured")
        if not api_key:
            raise AIClientError("OpenAI-compatible API key is not configured")
        if not model:
            raise AIClientError("OpenAI-compatible model is not configured")

        payload = self._openai_json_payload(
            system_prompt="You are a JSON-only health check.",
            user_prompt=(
                'Return strict JSON exactly like {"status":"ok","capability":"json"}.'
            ),
            model=model,
            temperature=temperature if temperature is not None else 0,
        )
        data = self._post_openai_json_with_config(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            payload=payload,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("LLM test response missing message content") from exc
        parsed = self._parse_json_content(content)
        if not isinstance(parsed, dict) or str(parsed.get("status", "")).lower() != "ok":
            raise AIClientError("LLM test response is JSON, but missing status=ok")
        return {
            "provider": "openai_compatible",
            "model": model,
            "message": "strict JSON ok",
        }

    def test_ollama_connection(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        if not base_url:
            raise AIClientError("Ollama base URL is not configured")
        if not model:
            raise AIClientError("Ollama model is not configured")
        payload = {
            "model": model,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else 0,
            },
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with exactly: ok",
                }
            ],
        }
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AIClientError(f"Ollama test request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise AIClientError(f"Ollama test request failed with status {status_code}") from exc
        except httpx.HTTPError as exc:
            raise AIClientError(f"Ollama test request failed: {exc}") from exc

        try:
            data = response.json()
            content = data["message"]["content"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AIClientError("Ollama test response missing message content") from exc
        return {
            "provider": "ollama",
            "model": model,
            "message": str(content).strip()[:200],
        }

    def _chat_openai_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float | None,
        timeout_seconds: float | None,
    ) -> dict[str, Any]:
        payload = self._openai_json_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature if temperature is not None else self.settings.llm_temperature,
        )
        data = self._post_openai_compatible(
            "/chat/completions",
            payload,
            timeout_seconds=timeout_seconds,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("LLM response missing message content") from exc
        return self._parse_json_content(content)

    def _chat_ollama_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float | None,
        timeout_seconds: float | None,
    ) -> dict[str, Any]:
        base_url = self.settings.ollama_base_url.rstrip("/")
        prompt = (
            f"{system_prompt}\n\n"
            "You must return exactly one JSON object and nothing else.\n\n"
            f"{user_prompt}"
        )
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

        try:
            with httpx.Client(timeout=timeout_seconds or self.settings.ollama_timeout_seconds) as client:
                response = client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIClientError(f"Ollama request failed: {exc}") from exc

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise AIClientError("Ollama response is not valid JSON payload") from exc

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AIClientError("Ollama response missing message content") from exc
        return self._parse_json_content(content)

    def _openai_json_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "You must return exactly one valid JSON object and no prose."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }

    def _post_openai_compatible(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.settings.llm_base_url:
            raise AIClientError("LLM_BASE_URL is not configured")
        if not self.settings.llm_api_key:
            raise AIClientError("LLM_API_KEY is not configured")

        return self._post_openai_json_with_config(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key,
            timeout_seconds=timeout_seconds or self.settings.llm_timeout_seconds,
            path=path,
            payload=payload,
        )

    def _post_openai_json_with_config(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        payload: dict[str, Any],
        path: str = "/chat/completions",
    ) -> dict[str, Any]:
        try:
            return self._post_openai_compatible_with_config(
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                path=path,
                payload=payload,
            )
        except AIClientError as exc:
            message = str(exc).lower()
            if "status 400" not in message and "status 422" not in message:
                raise
            retry_payload = dict(payload)
            retry_payload.pop("response_format", None)
            retry_payload["messages"] = [
                {
                    **message_item,
                    "content": (
                        f"{message_item.get('content', '')}\n\n"
                        "Important: return raw JSON only. Do not use Markdown."
                    ),
                }
                if message_item.get("role") == "system"
                else message_item
                for message_item in payload.get("messages", [])
                if isinstance(message_item, dict)
            ]
            return self._post_openai_compatible_with_config(
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                path=path,
                payload=retry_payload,
            )

    def _post_openai_compatible_with_config(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_base_url = base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    f"{normalized_base_url}{path}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AIClientError(f"LLM request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            detail = exc.response.text[:300].replace("\n", " ").strip()
            suffix = f": {detail}" if detail else ""
            raise AIClientError(f"LLM request failed with status {status_code}{suffix}") from exc
        except httpx.HTTPError as exc:
            raise AIClientError(f"LLM request failed: {exc}") from exc

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise AIClientError("LLM response is not valid JSON payload") from exc

    def _parse_json_content(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, str) or not content.strip():
            raise AIClientError("LLM returned empty content")

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            extracted = self._extract_json_object(content)
            if extracted is None:
                raise AIClientError("LLM response is not valid JSON")
            try:
                return json.loads(extracted)
            except json.JSONDecodeError as exc:
                raise AIClientError("Extracted LLM JSON is invalid") from exc

    def _extract_json_object(self, content: str) -> str | None:
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", content)
        if fenced:
            return fenced.group(1)

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return content[start : end + 1]

    def _should_try_ollama(self, exc: AIClientError) -> bool:
        if not self.settings.llm_fallback_enabled:
            return False
        message = str(exc).lower()
        retryable_markers = [
            "timed out",
            "status 502",
            "status 503",
            "status 504",
            "connect",
            "network",
            "response is not valid json payload",
            "response is not valid json",
            "missing message content",
        ]
        return any(marker in message for marker in retryable_markers)
