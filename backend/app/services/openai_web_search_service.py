from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings


WORLD_IMPORT_ERROR_MESSAGES = {
    "WEB_SEARCH_NOT_CONFIGURED": "尚未配置 OpenAI Web Search API Key 或模型。",
    "WEB_SEARCH_UNSUPPORTED": "当前提供商不支持原生联网搜索，请配置 OpenAI Web Search。",
    "AUTHENTICATION_FAILED": "OpenAI Web Search 鉴权失败，请检查 API Key。",
    "RATE_LIMITED": "OpenAI Web Search 触发限流，请稍后重试。",
    "NETWORK_UNAVAILABLE": "网络不可用，无法连接 OpenAI Web Search。",
    "SEARCH_TIMEOUT": "联网搜索超时，请稍后重试或降低目标人数。",
    "NO_RELEVANT_WORK": "没有找到与查询匹配的明确作品或人物世界。",
    "NO_CHARACTER_INFORMATION": "找到了作品线索，但没有提取到可导入的人物信息。",
    "EXTRACTION_FAILED": "搜索结果解析失败。",
    "INVALID_PROVIDER_RESPONSE": "OpenAI Web Search 返回格式无效。",
}


@dataclass
class WorldImportErrorDetail:
    code: str
    message: str
    retryable: bool
    stage: str
    technical_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorldImportError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        stage: str,
        retryable: bool,
        technical_summary: str = "",
    ) -> None:
        self.detail = WorldImportErrorDetail(
            code=code,
            message=WORLD_IMPORT_ERROR_MESSAGES.get(code, code),
            retryable=retryable,
            stage=stage,
            technical_summary=technical_summary[:500],
        )
        super().__init__(self.detail.message)


class OpenAIWebSearchService:
    """OpenAI Responses API + native web_search adapter.

    The returned payload is deliberately compact: factual summaries and source
    metadata only. It never stores long source excerpts or novel text.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def test_connection(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        api_key = (api_key if api_key is not None else self.settings.web_search_api_key).strip()
        base_url = (base_url if base_url is not None else self.settings.web_search_base_url).strip()
        model = (model if model is not None else self.settings.web_search_model).strip()
        timeout = timeout_seconds or self.settings.web_search_timeout_seconds
        self._validate_config(api_key=api_key, base_url=base_url, model=model)
        payload = {
            "model": model,
            "input": "Search the web for OpenAI and reply with JSON: {\"status\":\"ok\"}.",
            "tools": [{"type": "web_search"}],
        }
        data = self._post_responses(
            payload,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout,
            stage="connection_test",
        )
        return {
            "status": "ok",
            "provider": "openai_web_search",
            "model": model,
            "message": "web_search reachable",
            "response_id": data.get("id"),
        }

    def search_world(self, query: str, limit: int) -> dict[str, Any]:
        limit = max(1, min(50, int(limit)))
        api_key = self.settings.web_search_api_key.strip()
        base_url = self.settings.web_search_base_url.strip()
        model = self.settings.web_search_model.strip()
        self._validate_config(api_key=api_key, base_url=base_url, model=model)

        accessed_at = datetime.now(timezone.utc).isoformat()
        prompt = _search_prompt(query, limit)
        payload = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "你是人物世界导入助手。必须只输出一个 JSON 对象；"
                        "不得编造 URL，不得保存或复述长篇受版权保护文本。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "tools": [{"type": "web_search"}],
        }
        data = self._post_responses(
            payload,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=self.settings.web_search_timeout_seconds,
            stage="searching",
        )
        text, citations = _extract_response_text_and_citations(data)
        try:
            parsed = _parse_json_object(text)
        except ValueError as exc:
            raise WorldImportError(
                "EXTRACTION_FAILED",
                stage="extracting",
                retryable=True,
                technical_summary=str(exc),
            ) from exc

        result = _normalize_world_payload(
            parsed,
            query=query,
            limit=limit,
            accessed_at=accessed_at,
            response_citations=citations,
        )
        if result["disambiguation_options"]:
            result["status_hint"] = "needs_disambiguation"
            return result
        if not result["work"].get("title"):
            raise WorldImportError(
                "NO_RELEVANT_WORK",
                stage="searching",
                retryable=True,
                technical_summary="missing work.title",
            )
        if not result["candidates"]:
            raise WorldImportError(
                "NO_CHARACTER_INFORMATION",
                stage="extracting",
                retryable=True,
                technical_summary="no normalized candidates",
            )
        return result

    def _validate_config(self, *, api_key: str, base_url: str, model: str) -> None:
        if not api_key or not model:
            raise WorldImportError(
                "WEB_SEARCH_NOT_CONFIGURED",
                stage="configuration",
                retryable=False,
                technical_summary="api_key or model missing",
            )
        if not base_url.startswith(("http://", "https://")):
            raise WorldImportError(
                "WEB_SEARCH_NOT_CONFIGURED",
                stage="configuration",
                retryable=False,
                technical_summary="base_url must start with http:// or https://",
            )

    def _post_responses(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        stage: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    f"{base_url.rstrip('/')}/responses",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise WorldImportError(
                "SEARCH_TIMEOUT",
                stage=stage,
                retryable=True,
                technical_summary=exc.__class__.__name__,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:400].replace("\n", " ").strip()
            if status in {401, 403}:
                code, retryable = "AUTHENTICATION_FAILED", False
            elif status == 429:
                code, retryable = "RATE_LIMITED", True
            elif status in {400, 404, 422} and "web_search" in detail.lower():
                code, retryable = "WEB_SEARCH_UNSUPPORTED", False
            else:
                code, retryable = "NETWORK_UNAVAILABLE", True
            raise WorldImportError(
                code,
                stage=stage,
                retryable=retryable,
                technical_summary=f"HTTP {status}: {detail}",
            ) from exc
        except httpx.HTTPError as exc:
            raise WorldImportError(
                "NETWORK_UNAVAILABLE",
                stage=stage,
                retryable=True,
                technical_summary=exc.__class__.__name__,
            ) from exc
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise WorldImportError(
                "INVALID_PROVIDER_RESPONSE",
                stage=stage,
                retryable=True,
                technical_summary="response body is not JSON",
            ) from exc
        if not isinstance(data, dict):
            raise WorldImportError(
                "INVALID_PROVIDER_RESPONSE",
                stage=stage,
                retryable=True,
                technical_summary="top-level response is not an object",
            )
        return data


def _search_prompt(query: str, limit: int) -> str:
    return f"""
联网搜索用户输入的人物世界：{query}

请先识别作品/世界（标题、作者、版本/媒介、阵营/势力），再提取最多 {limit} 个人物。
如果实际只能找到少于 {limit} 人，就只返回真实找到的人数，不要补造。
每个人物必须至少关联一个真实搜索来源 URL，否则不要标记 verified。
不要输出长篇原文，只输出事实性短摘要与来源元数据。

只返回 JSON，结构：
{{
  "work": {{"title": "", "author": "", "version": "", "medium": "", "summary": ""}},
  "disambiguation_options": [
    {{"id": "short-id", "title": "", "author": "", "medium": "", "reason": "", "sources": [{{"title": "", "url": ""}}]}}
  ],
  "candidates": [
    {{
      "id": "stable-source-or-name-id",
      "name": "",
      "aliases": [],
      "summary": "",
      "faction": "",
      "traits": [],
      "motivations": [],
      "values": [],
      "abilities": [],
      "communication": [],
      "background": "",
      "confidence": 0.0,
      "sources": [{{"title": "", "url": ""}}]
    }}
  ],
  "relationships": [
    {{"source": "candidate-id-or-name", "target": "candidate-id-or-name", "type": "ally|family|rival|mentor|member|other", "directed": true, "strength": 0.0, "description": "", "confidence": 0.0, "sources": [{{"title": "", "url": ""}}]}}
  ]
}}
"""


def _extract_response_text_and_citations(data: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    texts: list[str] = []
    citations: list[dict[str, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") in {"output_text", "text"} and isinstance(value.get("text"), str):
                texts.append(value["text"])
            for annotation in value.get("annotations", []) or []:
                if isinstance(annotation, dict):
                    url = str(annotation.get("url") or "")
                    if url.startswith(("http://", "https://")):
                        citations.append(
                            {
                                "url": url,
                                "title": str(annotation.get("title") or url),
                            }
                        )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data.get("output", data))
    if not texts and isinstance(data.get("output_text"), str):
        texts.append(data["output_text"])
    return "\n".join(texts).strip(), _dedupe_sources(citations)


def _parse_json_object(text: str) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("empty output text")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
        extracted = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
        if not extracted or not extracted.startswith("{"):
            raise ValueError("no JSON object found")
        payload = json.loads(extracted)
    if not isinstance(payload, dict):
        raise ValueError("JSON payload is not an object")
    return payload


def _normalize_world_payload(
    payload: dict[str, Any],
    *,
    query: str,
    limit: int,
    accessed_at: str,
    response_citations: list[dict[str, str]],
) -> dict[str, Any]:
    work = payload.get("work") if isinstance(payload.get("work"), dict) else {}
    options = [
        _normalize_option(item, response_citations)
        for item in _as_list(payload.get("disambiguation_options"))[:8]
        if isinstance(item, dict)
    ]
    candidates = []
    for item in _as_list(payload.get("candidates"))[:limit]:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_candidate(item, response_citations, accessed_at)
        if normalized["verification_status"] == "web_verified":
            candidates.append(normalized)
    relationships = [
        _normalize_relationship(item, response_citations, accessed_at)
        for item in _as_list(payload.get("relationships"))[:100]
        if isinstance(item, dict)
    ]
    return {
        "query": query,
        "work": {
            "title": str(work.get("title") or "").strip(),
            "author": str(work.get("author") or "").strip(),
            "version": str(work.get("version") or "").strip(),
            "medium": str(work.get("medium") or "").strip(),
            "summary": _short_text(work.get("summary"), 600),
        },
        "disambiguation_options": options,
        "candidates": candidates,
        "relationships": relationships,
        "errors": [],
        "source_failures": [],
        "accessed_at": accessed_at,
        "partial": False,
        "fallback_mode": "none",
    }


def _normalize_option(item: dict[str, Any], citations: list[dict[str, str]]) -> dict[str, Any]:
    sources = _normalize_sources(item.get("sources"), citations, "")
    return {
        "id": _slug(str(item.get("id") or item.get("title") or "work")),
        "title": str(item.get("title") or "").strip(),
        "author": str(item.get("author") or "").strip(),
        "medium": str(item.get("medium") or "").strip(),
        "reason": _short_text(item.get("reason"), 300),
        "sources": sources,
    }


def _normalize_candidate(
    item: dict[str, Any],
    citations: list[dict[str, str]],
    accessed_at: str,
) -> dict[str, Any]:
    name = str(item.get("name") or "").strip()
    sources = _normalize_sources(item.get("sources"), citations, name)
    candidate_id = _slug(str(item.get("id") or name))
    return {
        "id": candidate_id,
        "name": name,
        "aliases": _strings(item.get("aliases"))[:12],
        "summary": _short_text(item.get("summary"), 500) or "来源未提供摘要。",
        "traits": _strings(item.get("traits"))[:10],
        "motivations": _strings(item.get("motivations"))[:10],
        "values": _strings(item.get("values"))[:10],
        "abilities": _strings(item.get("abilities"))[:12],
        "communication": _strings(item.get("communication"))[:8],
        "faction": _short_text(item.get("faction"), 128) or None,
        "background": _short_text(item.get("background"), 600) or None,
        "source_type": "openai_web_search",
        "source_ref": candidate_id,
        "sources": sources,
        "verification_status": "web_verified" if sources else "generated_unverified",
        "confidence": _clamp_float(item.get("confidence"), 0.75 if sources else 0.35),
        "accessed_at": accessed_at,
    }


def _normalize_relationship(
    item: dict[str, Any],
    citations: list[dict[str, str]],
    accessed_at: str,
) -> dict[str, Any]:
    sources = _normalize_sources(item.get("sources"), citations, "")
    return {
        "source": _slug(str(item.get("source") or "")),
        "target": _slug(str(item.get("target") or "")),
        "type": _short_text(item.get("type"), 64) or "other",
        "directed": bool(item.get("directed", True)),
        "strength": _clamp_float(item.get("strength"), 0.5),
        "description": _short_text(item.get("description"), 500),
        "confidence": _clamp_float(item.get("confidence"), 0.6 if sources else 0.35),
        "source_type": "openai_web_search" if sources else "generated_unverified",
        "source_ref": sources[0]["url"][:255] if sources else None,
        "sources": sources,
        "accessed_at": accessed_at,
    }


def _normalize_sources(value: Any, response_citations: list[dict[str, str]], hint: str) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        sources.append({"url": url, "title": str(item.get("title") or url).strip()[:255]})
    if not sources and hint:
        lowered = hint.lower()
        sources = [
            item for item in response_citations
            if lowered in item.get("title", "").lower()
        ][:2]
    return _dedupe_sources(sources)[:5]


def _dedupe_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in sources:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({"url": url, "title": str(item.get("title") or url).strip()[:255]})
    return result


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [_short_text(item, 120) for item in _as_list(value) if _short_text(item, 120)]


def _short_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _clamp_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(0.0, min(1.0, number)), 3)


def _slug(value: str) -> str:
    cleaned = re.sub(r"\s+", "-", value.strip().lower())
    cleaned = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_-]+", "", cleaned)
    return cleaned[:80] or "unknown"
