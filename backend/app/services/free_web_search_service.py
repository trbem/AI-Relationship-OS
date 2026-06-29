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

    def search_world(
        self,
        query: str,
        limit: int,
        language: str = "zh",
    ) -> dict[str, Any]:
        limit = max(1, min(50, int(limit)))
        target_language = _resolve_language(language, query)
        accessed_at = datetime.now(timezone.utc).isoformat()
        sources, failures = self._collect_sources(query, target_language)
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
                user_prompt=_extraction_prompt(
                    query,
                    limit,
                    sources,
                    target_language,
                ),
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
        normalized["language"] = target_language
        normalized["source_failures"] = failures
        normalized["partial"] = bool(failures)
        if _needs_language_rewrite(normalized, target_language):
            normalized = self._rewrite_language(
                normalized,
                query=query,
                limit=limit,
                accessed_at=accessed_at,
                sources=sources,
                language=target_language,
                failures=failures,
            )
        for candidate in normalized.get("candidates", []):
            candidate["source_type"] = "free_web"
            candidate["source_ref"] = candidate["id"]
        for relationship in normalized.get("relationships", []):
            if relationship.get("sources"):
                relationship["source_type"] = "free_web"
        disambiguation_options = normalized.get("disambiguation_options", [])
        if len(disambiguation_options) == 1 and normalized.get("candidates"):
            normalized["selected_disambiguation"] = disambiguation_options[0]
            normalized["disambiguation_options"] = []
        elif disambiguation_options:
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

    def _rewrite_language(
        self,
        normalized: dict[str, Any],
        *,
        query: str,
        limit: int,
        accessed_at: str,
        sources: list[WebSource],
        language: str,
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            payload = AIClient().chat_json(
                system_prompt=(
                    "Rewrite the supplied character-world JSON into the target "
                    "language. Preserve ids, source URLs, source titles, "
                    "verification status, confidence values, and relationships. "
                    "Do not add fake sources or new characters."
                ),
                user_prompt=_rewrite_prompt(normalized, language),
                temperature=0.0,
                timeout_seconds=90,
            )
        except AIClientError:
            return normalized
        rewritten = _normalize_world_payload(
            payload,
            query=query,
            limit=limit,
            accessed_at=accessed_at,
            response_citations=[
                {"title": source.title, "url": source.url}
                for source in sources
            ],
        )
        rewritten["provider"] = "free_web"
        rewritten["source_type"] = "free_web"
        rewritten["language"] = language
        rewritten["source_failures"] = failures
        rewritten["partial"] = bool(failures)
        return rewritten

    def _collect_sources(
        self,
        query: str,
        language: str = "zh",
    ) -> tuple[list[WebSource], list[dict[str, Any]]]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 RelationshipOS/0.8.4"
            )
        }
        failures: list[dict[str, Any]] = []
        candidates: list[WebSource] = []
        with httpx.Client(
            timeout=httpx.Timeout(SEARCH_TIMEOUT_SECONDS, connect=8.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            for search_query in _search_queries(query, language):
                try:
                    candidates.extend(_duckduckgo_search(client, search_query))
                except httpx.HTTPError as exc:
                    failures.append(_failure("duckduckgo", "searching", exc))
                wiki_langs = ["zh", "en"] if language == "zh" else ["en", "zh"]
                for wiki_lang in wiki_langs:
                    try:
                        candidates.extend(_wikipedia_search(client, search_query, wiki_lang))
                        candidates.extend(_wikidata_search(client, search_query, wiki_lang))
                    except httpx.HTTPError as exc:
                        failures.append(
                            _failure(f"wikipedia/wikidata:{wiki_lang}", "searching", exc)
                        )
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


def _resolve_language(language: str, query: str) -> str:
    value = (language or "zh").strip().lower()
    if value == "auto":
        return "zh" if re.search(r"[\u4e00-\u9fff]", query) else "en"
    if value in {"zh", "en"}:
        return value
    return "zh"


def _search_queries(query: str, language: str = "zh") -> list[str]:
    clean = query.strip()
    if language == "en":
        suffixes = [
            "characters",
            "characters list",
            "main characters",
            "cast",
            "relationships",
        ]
    else:
        suffixes = [
            "人物",
            "角色",
            "主要人物",
            "人物关系",
            "角色介绍",
            "characters list",
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
        if (
            not url
            or url in seen_urls
            or title_key in seen_titles
            or _is_low_quality_source(url, item.title)
        ):
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


def _is_low_quality_source(url: str, title: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    title_value = title.lower()
    if host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.tiktok.com",
        "tiktok.com",
    }:
        return True
    if "youtube.com" in host or "youtu.be" in host:
        return True
    if any(token in path for token in ["/video/", "/watch", "/shorts/"]):
        return True
    return "trailer" in title_value or "episode clip" in title_value


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


def _language_label(language: str) -> str:
    return "Simplified Chinese" if language == "zh" else "English"


def _extraction_prompt(
    query: str,
    limit: int,
    sources: list[WebSource],
    language: str = "zh",
) -> str:
    source_payload = [source.to_prompt_dict() for source in sources]
    target = _language_label(language)
    return f"""
The user wants to import a character world for: {query}

Below are web sources collected by the application. Use only these sources to
identify the work/world and extract up to {limit} character candidates. If the
sources only support fewer people, return fewer people. Every character must
cite at least one URL from the supplied sources. Do not invent URLs. Do not copy
long original passages; only output short factual summaries.

Target output language: {target}.
All user-facing fields must use {target}: work title/summary, disambiguation
title/reason, character names when a common translated name exists, aliases,
factions, summaries, traits, motivations, values, abilities, communication,
background, and relationship descriptions. Source titles and URLs may stay in
their original language. If sources are English but the target is Simplified
Chinese, translate and summarize the facts into Chinese.

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


def _rewrite_prompt(payload: dict[str, Any], language: str) -> str:
    target = _language_label(language)
    return f"""
Target output language: {target}.
Rewrite this JSON so all user-facing text uses the target language. Preserve
ids, URLs, source arrays, verification metadata, and confidence values exactly
when possible. Return only the rewritten JSON object.

JSON:
{json.dumps(payload, ensure_ascii=False)}
"""


def _needs_language_rewrite(payload: dict[str, Any], language: str) -> bool:
    if language != "zh":
        return False
    texts: list[str] = []
    work = payload.get("work") if isinstance(payload.get("work"), dict) else {}
    texts.extend(str(work.get(key) or "") for key in ("title", "summary", "medium"))
    for candidate in payload.get("candidates", [])[:8]:
        if not isinstance(candidate, dict):
            continue
        texts.extend(
            str(candidate.get(key) or "")
            for key in ("name", "summary", "faction", "background")
        )
        for key in ("traits", "motivations", "values", "abilities"):
            value = candidate.get(key)
            if isinstance(value, list):
                texts.extend(str(item) for item in value[:3])
    combined = " ".join(texts).strip()
    if len(combined) < 40:
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", combined))
    alpha_count = len(re.findall(r"[A-Za-z]", combined))
    return alpha_count > 80 and cjk_count < max(8, alpha_count // 8)


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
