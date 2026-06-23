from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import WorldImportTask
from app.services.openai_web_search_service import WORLD_IMPORT_ERROR_MESSAGES


INCOMPLETE_WORLD_IMPORT_STATUSES = {
    "queued",
    "searching",
    "extracting",
    "running",
    "pending",
}


def resume_incomplete_world_imports() -> None:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(WorldImportTask).where(
                WorldImportTask.status.in_(INCOMPLETE_WORLD_IMPORT_STATUSES)
            )
        ).all()
        for task in rows:
            task.status = "failed"
            task.stage = "resume"
            task.progress = 1.0
            task.error = (
                '{"code":"NETWORK_UNAVAILABLE",'
                f'"message":"{WORLD_IMPORT_ERROR_MESSAGES["NETWORK_UNAVAILABLE"]}",'
                '"retryable":true,'
                '"stage":"resume",'
                '"technical_summary":"task interrupted by application restart"}'
            )
        db.commit()
    finally:
        db.close()


RELATION_PROPERTIES = {
    "P22": "父亲",
    "P25": "母亲",
    "P26": "配偶",
    "P40": "子女",
    "P3373": "兄弟姐妹",
    "P463": "所属组织",
    "P108": "任职",
}


class WorldImportService:
    def search(self, query: str, limit: int) -> dict:
        limit = max(1, min(40, limit))
        candidates: list[dict] = []
        errors: list[str] = []
        source_failures: list[dict] = []
        headers = {
            "User-Agent": "RelationshipOS/0.4 (local desktop app)",
            "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        }
        timeout = httpx.Timeout(12.0, connect=5.0)
        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
            search_items = self._search_wikidata(client, query, limit, errors, source_failures)
            fallback_items: list[dict] = []
            if not search_items:
                fallback_items = self._search_wikipedia(
                    client, query, limit, errors, source_failures
                )
                search_items = fallback_items
            for item in search_items:
                qid = item["id"]
                name = item.get("label") or qid
                summary = item.get("description") or ""
                wiki_url = item.get("wikipedia_url") or f"https://zh.wikipedia.org/wiki/{quote(name)}"
                wiki_payload = self._wikipedia_summary(
                    client,
                    name,
                    qid,
                    errors,
                    source_failures,
                )
                if wiki_payload:
                    summary = wiki_payload.get("extract") or summary
                    wiki_url = (
                        wiki_payload.get("content_urls", {})
                        .get("desktop", {})
                        .get("page", wiki_url)
                    )
                candidates.append(
                    {
                        "id": qid,
                        "name": name,
                        "aliases": [alias for alias in item.get("aliases", []) if alias != name],
                        "summary": summary,
                        "description": item.get("description") or "",
                        "source_type": item.get("source_type", "wikidata"),
                        "source_ref": qid,
                        "sources": [
                            {
                                "source_type": item.get("source_type", "wikidata"),
                                "external_id": qid,
                                "url": item.get("concepturi") or wiki_url,
                                "title": name,
                            },
                            {
                                "source_type": "wikipedia",
                                "external_id": qid,
                                "url": wiki_url,
                                "title": name,
                            },
                        ],
                    }
                )
        return {
            "query": query,
            "candidates": candidates,
            "relationships": [],
            "errors": errors,
            "source_failures": source_failures,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "partial": bool(errors),
        }

    def _search_wikidata(
        self,
        client: httpx.Client,
        query: str,
        limit: int,
        errors: list[str],
        source_failures: list[dict],
    ) -> list[dict]:
        try:
            response = client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "zh",
                    "uselang": "zh",
                    "format": "json",
                    "limit": limit,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            errors.append(f"Wikidata search failed with status {status}")
            source_failures.append({"source": "wikidata", "stage": "search", "status": status})
            return []
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"Wikidata search unavailable: {exc.__class__.__name__}")
            source_failures.append({"source": "wikidata", "stage": "search", "status": None})
            return []
        return [item for item in payload.get("search", []) if isinstance(item, dict)]

    def _search_wikipedia(
        self,
        client: httpx.Client,
        query: str,
        limit: int,
        errors: list[str],
        source_failures: list[dict],
    ) -> list[dict]:
        try:
            response = client.get(
                "https://zh.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "namespace": 0,
                    "limit": limit,
                    "format": "json",
                },
            )
        except httpx.HTTPError as exc:
            errors.append(f"Wikipedia fallback search unavailable: {exc.__class__.__name__}")
            source_failures.append({"source": "wikipedia", "stage": "opensearch", "status": None})
            return []
        if response.status_code != 200:
            errors.append(f"Wikipedia fallback search failed with status {response.status_code}")
            source_failures.append(
                {"source": "wikipedia", "stage": "opensearch", "status": response.status_code}
            )
            return []
        try:
            payload = response.json()
        except ValueError:
            errors.append("Wikipedia fallback search returned invalid JSON")
            return []
        titles = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        descriptions = payload[2] if isinstance(payload, list) and len(payload) > 2 else []
        urls = payload[3] if isinstance(payload, list) and len(payload) > 3 else []
        items = []
        for index, title in enumerate(titles[:limit]):
            if not isinstance(title, str) or not title.strip():
                continue
            url = urls[index] if index < len(urls) and isinstance(urls[index], str) else ""
            description = (
                descriptions[index]
                if index < len(descriptions) and isinstance(descriptions[index], str)
                else ""
            )
            items.append(
                {
                    "id": f"wikipedia:{title}",
                    "label": title,
                    "description": description,
                    "aliases": [],
                    "source_type": "wikipedia",
                    "concepturi": url or f"https://zh.wikipedia.org/wiki/{quote(title)}",
                    "wikipedia_url": url or f"https://zh.wikipedia.org/wiki/{quote(title)}",
                }
            )
        if items:
            errors.append("Wikidata unavailable; used Wikipedia fallback search")
        return items

    def _wikipedia_summary(
        self,
        client: httpx.Client,
        name: str,
        qid: str,
        errors: list[str],
        source_failures: list[dict],
    ) -> dict | None:
        try:
            response = client.get(
                f"https://zh.wikipedia.org/api/rest_v1/page/summary/{quote(name)}"
            )
        except httpx.HTTPError as exc:
            errors.append(f"{name}: Wikipedia summary unavailable ({exc.__class__.__name__})")
            source_failures.append(
                {
                    "source": "wikipedia",
                    "stage": "summary",
                    "status": None,
                    "external_id": qid,
                }
            )
            return None
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                errors.append(f"{name}: Wikipedia summary returned invalid JSON")
                return None
        if response.status_code in {403, 404, 408, 429, 500, 502, 503, 504}:
            errors.append(f"{name}: Wikipedia summary failed with status {response.status_code}")
            source_failures.append(
                {
                    "source": "wikipedia",
                    "stage": "summary",
                    "status": response.status_code,
                    "external_id": qid,
                }
            )
        return None
