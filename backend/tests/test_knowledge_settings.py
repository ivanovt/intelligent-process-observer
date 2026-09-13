from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_knowledge_settings_have_approved_server_only_defaults() -> None:
    settings = Settings()

    assert settings.knowledge_embedding_model == "openai/text-embedding-3-small"
    assert settings.knowledge_embedding_dimensions == 1_536
    assert settings.knowledge_upload_max_bytes == 10 * 1024 * 1024
    assert settings.knowledge_extraction_max_characters == 1_000_000
    assert settings.knowledge_embedding_batch_size == 32
    assert settings.knowledge_retrieval_max_passages == 4
    assert settings.knowledge_retrieval_max_serialized_bytes == 8_192
    assert settings.knowledge_retrieval_timeout_seconds == 30
    assert settings.knowledge_scope_suggestion_model == "openai/gpt-5.6-terra"


def test_knowledge_settings_accept_configurable_server_side_overrides() -> None:
    settings = Settings(
        knowledge_embedding_model="provider/embedding-model",
        knowledge_upload_max_bytes=1_024,
        knowledge_extraction_max_characters=2_048,
        knowledge_embedding_batch_size=2,
        knowledge_scope_suggestion_model="provider/suggestion-model",
    )

    assert settings.knowledge_embedding_model == "provider/embedding-model"
    assert settings.knowledge_upload_max_bytes == 1_024
    assert settings.knowledge_extraction_max_characters == 2_048
    assert settings.knowledge_embedding_batch_size == 2
    assert settings.knowledge_scope_suggestion_model == "provider/suggestion-model"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("knowledge_embedding_model", ""),
        ("knowledge_upload_max_bytes", 0),
        ("knowledge_extraction_max_characters", 0),
        ("knowledge_embedding_batch_size", 0),
        ("knowledge_scope_suggestion_model", ""),
    ],
)
def test_knowledge_settings_reject_non_positive_or_blank_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("knowledge_embedding_dimensions", 768),
        ("knowledge_embedding_dimensions", 1_537),
        ("knowledge_retrieval_max_passages", 2),
        ("knowledge_retrieval_max_passages", 5),
        ("knowledge_retrieval_max_serialized_bytes", 4_096),
        ("knowledge_retrieval_max_serialized_bytes", 8_193),
        ("knowledge_retrieval_timeout_seconds", 15.5),
        ("knowledge_retrieval_timeout_seconds", 30.1),
    ],
)
def test_knowledge_settings_reject_incompatible_fixed_mvp_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})
