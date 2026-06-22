from app.config import Settings


def test_mimo_and_local_embedding_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.completion_model == "mimo-v2.5"
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_model == "mimo-v2.5"
    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "local-hash-v1"
