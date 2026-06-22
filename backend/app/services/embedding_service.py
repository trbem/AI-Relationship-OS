import hashlib
import math
import re
from typing import Sequence

import httpx

from app.config import get_settings


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_embedding(self, text: str, model: str | None = None) -> list[float]:
        selected_model = model or self.settings.embedding_model
        if self.settings.embedding_provider.lower() == "local":
            return self._fallback_vector(text)
        if self.settings.embedding_provider.lower() != "openai":
            raise ValueError(
                f"Unsupported embedding provider: {self.settings.embedding_provider}"
            )
        if not self.settings.llm_base_url:
            return self._fallback_vector(text)
        try:
            return self._call_embeddings_api(text, selected_model)
        except Exception:
            return self._fallback_vector(text)

    def batch_embeddings(self, texts: Sequence[str], model: str | None = None) -> list[list[float]]:
        return [self.build_embedding(text, model=model) for text in texts]

    def _call_embeddings_api(self, text: str, model: str) -> list[float]:
        base_url = self.settings.llm_base_url.rstrip("/")
        payload = {
            "model": model,
            "input": text[:4000],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
            response = client.post(f"{base_url}/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            return data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Embeddings API response missing embedding") from exc

    @staticmethod
    def _fallback_vector(text: str) -> list[float]:
        dimensions = 1536
        vector = [0.0] * dimensions
        normalized = text.strip().lower()
        if not normalized:
            return vector

        words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        features = words + [
            normalized[index : index + 3]
            for index in range(max(len(normalized) - 2, 0))
        ]
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
