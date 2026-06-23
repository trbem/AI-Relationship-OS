from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from app.services.ai_client import AIClient, AIClientError
from app.services.openai_web_search_service import (
    WorldImportError,
    _normalize_world_payload,
)


SEARCH_TIMEOUT_SECONDS = 20.0
FETCH_TIMEOUT_SECONDS = 12.0
MAX_SEARCH_SOURCES = 20


@dataclass
class WebSource:
    title: str
    url: str
    snippet: str = ""
    excerpt: str = ""

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "title": self.title[:240],
            "url": self.url,
            "snippet": self.snippet[:500],
            "excerpt": self.excerpt[:1200],
        }


class FreeWebWorldSearchService:
    """Free web search plus current-model extraction for persona worlds.

    The implementation stays lightweight for the Windows package: it uses
    public HTML/API endpoints, fetches short excerpts, then asks the currently
    configured AI provider to extract structured candidates. It does not depend
    on OpenAI native Web Search or on a browser engine.
    """

    def search_world(self, query: str, limit: int) -> dict[str, Any]:
        limit = max(1, min(50, int(limit)))
        accessed_at = datetime.now(timezone.utc).isoformat()
        sources, failures = self._collect_sources(query)
        if not sources:
            raise WorldImportError(
                "NO_RELEVANT_WORK",
                stage="searching",
                retryable=True,
                technical_summary="free web search returned no usable sources",
            )

        try:
            payload = AIClient().chat_json(
                system_prompt=(
                    "You are a character-world import assistant. Extract only "
                    "short factual summaries from the supplied web search "
                    "sources. Return a single JSON object. Do not invent URLs "
                    "and do not reproduce long copyrighted text."
                ),
                user_prompt=_extraction_prompt(query, limit, sources),
                temperature=0.1,
                timeout_seconds=120,
            )
        except AIClientError as exc:
            raise WorldImportError(
                "EXTRACTION_FAILED",
                stage="extracting",
                retryable=True,
                technical_summary=str(exc)[:300],
            ) from exc

        normalized = _normalize_world_payload(
            payload,
            query=query,
            limit=limit,
            accessed_at=accessed_at,
            response_citations=[
                {"title": source.title, "url": source.url}
                for source in sources
            ],
        )
        normalized["provider"] = "free_web"
        normalized["source_type"] = "free_web"
        normalized["source_failures"] = failures
        normalized["partial"] = bool(failures)
        for candidate in normalized.get("candidates", []):
            candidate["source_type"] = "free_web"
            candidate["source_ref"] = candidate["id"]
        for relationship in normalized.get("relationships", []):
            if relationship.get("sources"):
                relationship["source_type"] = "free_web"
        if normalized["disambiguation_options"]:
            normalized["status_hint"] = "needs_disambiguation"
            return normalized
        if not normalized["work"].get("title"):
            raise WorldImportError(
                "NO_RELEVANT_WORK",
                stage="extracting",
                retryable=True,
                technical_summary="extracted payload missing work.title",
            )
        if not normalized["candidates"]:
            raise WorldImportError(
                "NO_CHARACTER_INFORMATION",
                stage="extracting",
                retryable=True,
                technical_summary="no source-verified candidates extracted",
            )
        return normalized

    def _collect_sources(self, query: str) -> tuple[list[WebSource], list[dict[str, Any]]]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 RelationshipOS/0.8.2"
            )
        }
        failures: list[dict[str, Any]] = []
        candidates: list[WebSource] = []
        with httpx.Client(
            timeout=httpx.Timeout(SEARCH_TIMEOUT_SECONDS, connect=8.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            for search_query in _search_queries(query):
                try:
                    candidates.extend(_duckduckgo_search(client, search_query))
                except httpx.HTTPError as exc:
                    failures.append(_failure("duckduckgo", "searching", exc))
                try:
                    candidates.extend(_wikipedia_search(client, search_query, "zh"))
                    candidates.extend(_wikipedia_search(client, search_query, "en"))
                    candidates.extend(_wikidata_search(client, search_query, "zh"))
                    candidates.extend(_wikidata_search(client, search_query, "en"))
                except httpx.HTTPError as exc:
                    failures.append(_failure("wikipedia/wikidata", "searching", exc))
                if len(_dedupe_sources(candidates)) >= MAX_SEARCH_SOURCES:
                    break

            deduped = _dedupe_sources(candidates)[:MAX_SEARCH_SOURCES]
            enriched: list[WebSource] = []
            for source in deduped:
                try:
                    enriched.append(_fetch_excerpt(client, source))
                except httpx.HTTPError as exc:
                    failures.append(_failure(source.url, "fetching", exc))
                    enriched.append(source)
        return enriched[:MAX_SEARCH_SOURCES], failures


def _search_queries(query: str) -> list[str]:
    clean = query.strip()
    suffixes = [
        "人物 角色 列表",
        "主要人物",
        "角色介绍",
        "characters list cast",
    ]
    values = [clean, *[f"{clean} {suffix}" for suffix in suffixes]]
    return list(dict.fromkeys(values))


def _duckduckgo_search(client: httpx.Client, query: str) -> list[WebSource]:
    response = client.get(f"https://duckduckgo.com/html/?q={quote_plus(query)}")
    response.raise_for_status()
    parser = _DuckDuckGoParser()
    parser.feed(response.text)
    return parser.results[:8]


def _wikipedia_search(client: httpx.Client, query: str, lang: str) -> list[WebSource]:
    response = client.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "opensearch",
            "namespace": "0",
            "limit": "5",
            "format": "json",
            "search": query,
        },
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or len(data) < 4:
        return []
    titles = data[1] if isinstance(data[1], list) else []
    snippets = data[2] if isinstance(data[2], list) else []
    urls = data[3] if isinstance(data[3], list) else []
    results: list[WebSource] = []
    for title, snippet, url in zip(titles, snippets, urls):
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            results.append(
                WebSource(
                    title=str(title or url),
                    url=url,
                    snippet=str(snippet or ""),
                )
            )
    return results


def _wikidata_search(client: httpx.Client, query: str, lang: str) -> list[WebSource]:
    response = client.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "format": "json",
            "language": lang,
            "uselang": lang,
            "limit": "5",
            "search": query,
        },
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("search", []) if isinstance(data, dict) else []
    results: list[WebSource] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("id") or "").strip()
        if not entity_id:
            continue
        title = str(item.get("label") or entity_id)
        description = str(item.get("description") or "")
        results.append(
            WebSource(
                title=title,
                url=f"https://www.wikidata.org/wiki/{entity_id}",
                snippet=description,
            )
        )
    return results


def _fetch_excerpt(client: httpx.Client, source: WebSource) -> WebSource:
    response = client.get(source.url, timeout=FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return source
    title, text = _extract_html_text(response.text)
    return WebSource(
        title=title or source.title,
        url=source.url,
        snippet=source.snippet,
        excerpt=text[:1200],
    )


def _extract_html_text(markup: str) -> tuple[str, str]:
    parser = _ReadableHtmlParser()
    parser.feed(markup)
    text = html.unescape(" ".join(parser.text_parts))
    text = re.sub(r"\s+", " ", text).strip()
    return parser.title.strip(), text


def _dedupe_sources(values: list[WebSource]) -> list[WebSource]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[WebSource] = []
    for item in values:
        url = _clean_url(item.url)
        title_key = re.sub(r"\s+", " ", item.title).strip().lower()
        if not url or url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        result.append(
            WebSource(
                title=item.title.strip() or url,
                url=url,
                snippet=item.snippet.strip(),
            )
        )
    return result


def _clean_url(url: str) -> str:
    value = html.unescape(str(url or "")).strip()
    if value.startswith("//duckduckgo.com/l/") or value.startswith(
        "https://duckduckgo.com/l/"
    ):
        parsed = urlparse(value)
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        value = unquote(target) if target else value
    if not value.startswith(("http://", "https://")):
        return ""
    parsed = urlparse(value)
    return parsed._replace(fragment="").geturl()


def _failure(source: str, stage: str, exc: Exception) -> dict[str, Any]:
    status = None
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
    return {
        "source": source[:160],
        "stage": stage,
        "status": status,
        "error": exc.__class__.__name__,
    }


def _extraction_prompt(query: str, limit: int, sources: list[WebSource]) -> str:
    source_payload = [source.to_prompt_dict() for source in sources]
    return f"""
The user wants to import a character world for: {query}

Below are web sources collected by the application. Use only these sources to
identify the work/world and extract up to {limit} character candidates. If the
sources only support fewer people, return fewer people. Every character must
cite at least one URL from the supplied sources. Do not invent URLs. Do not copy
long original passages; only output short factual summaries.

Source JSON:
{json.dumps(source_payload, ensure_ascii=False)}

Return only one JSON object with this shape:
{{
  "work": {{"title": "", "author": "", "version": "", "medium": "", "summary": ""}},
  "disambiguation_options": [
    {{"id": "short-id", "title": "", "author": "", "medium": "", "reason": "", "sources": [{{"title": "", "url": ""}}]}}
  ],
  "candidates": [
    {{
      "id": "stable-id",
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


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[WebSource] = []
        self._in_link = False
        self._in_snippet = False
        self._current_href = ""
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = attr.get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self._in_link = True
            self._current_href = attr.get("href", "") or ""
            self._current_title = []
        elif "result__snippet" in classes:
            self._in_snippet = True
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._current_title.append(data)
        if self._in_snippet:
            self._current_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            self._in_link = False
            url = _clean_url(self._current_href)
            title = html.unescape(" ".join(self._current_title)).strip()
            if url and title:
                self.results.append(WebSource(title=title, url=url))
        elif self._in_snippet and tag in {"a", "div"}:
            self._in_snippet = False
            snippet = html.unescape(" ".join(self._current_snippet)).strip()
            if snippet and self.results:
                self.results[-1].snippet = snippet


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += f" {text}"
        elif not self._skip_depth and len(text) > 1:
            self.text_parts.append(text)
