import math
from types import SimpleNamespace

from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService


def test_fallback_embedding_is_finite_normalized_and_semantically_stable() -> None:
    first = EmbeddingService._fallback_vector("project progress report")
    second = EmbeddingService._fallback_vector("project progress update")
    unrelated = EmbeddingService._fallback_vector("holiday dinner menu")

    assert len(first) == 1536
    assert all(math.isfinite(value) for value in first)
    assert math.isclose(sum(value * value for value in first), 1.0)
    assert RetrievalService._cosine_similarity(first, second) > (
        RetrievalService._cosine_similarity(first, unrelated)
    )


def test_local_provider_never_calls_remote_embeddings(monkeypatch) -> None:
    service = EmbeddingService.__new__(EmbeddingService)
    service.settings = SimpleNamespace(
        embedding_provider="local",
        embedding_model="local-hash-v1",
        llm_base_url="https://api.example.test/v1",
    )

    def fail_remote(*_args, **_kwargs):
        raise AssertionError("remote embeddings must not be called")

    monkeypatch.setattr(service, "_call_embeddings_api", fail_remote)

    assert len(service.build_embedding("project progress")) == 1536
