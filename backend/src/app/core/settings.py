from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class BearerTokenCredentials(BaseModel):
    type: Literal["bearer_token"]
    token: SecretStr


class BasicAuthCredentials(BaseModel):
    type: Literal["basic_auth"]
    username: str
    password: SecretStr


PrometheusCredentials = Annotated[
    BearerTokenCredentials | BasicAuthCredentials,
    Field(discriminator="type"),
]


class PrometheusSourceSettings(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    credentials: PrometheusCredentials


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://ipo:ipo@localhost:5432/ipo"
    prometheus_sources: list[PrometheusSourceSettings] = Field(default_factory=list)
    # Jira parsing remains provider-owned so malformed optional integration input cannot
    # prevent unrelated application startup.
    jira_alert_provider_raw: str | None = Field(
        default=None, validation_alias="JIRA_ALERT_PROVIDER"
    )
    openrouter_api_key: SecretStr | None = None
    metric_analysis_model: str = Field(default="openai/gpt-5.6-terra", min_length=1)
    alert_analysis_model: str = Field(default="openai/gpt-5.6-terra", min_length=1)
    observation_reasoning_model: str = Field(default="openai/gpt-5.6-terra", min_length=1)
    observation_report_model: str = Field(default="openai/gpt-5.6-terra", min_length=1)
    openrouter_request_timeout_seconds: float = Field(default=120, gt=0)
    metric_analysis_request_timeout_seconds: float = Field(default=120, gt=0)
    alert_analysis_request_timeout_seconds: float = Field(default=120, gt=0)
    metric_analysis_max_output_tokens: int = Field(default=12_288, gt=0)
    alert_analysis_max_output_tokens: int = Field(default=12_288, gt=0)
    observation_reasoning_max_output_tokens: int = Field(default=12_288, gt=0)
    observation_report_max_output_tokens: int = Field(default=8_192, gt=0)
    knowledge_embedding_model: str = Field(default="openai/text-embedding-3-small", min_length=1)
    knowledge_embedding_dimensions: int = Field(default=1_536, gt=0)
    knowledge_upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    knowledge_extraction_max_characters: int = Field(default=1_000_000, gt=0)
    knowledge_embedding_batch_size: int = Field(default=32, gt=0)
    knowledge_retrieval_max_passages: int = Field(default=4, gt=0)
    knowledge_retrieval_max_serialized_bytes: int = Field(default=8_192, gt=0)
    knowledge_retrieval_timeout_seconds: float = Field(default=30, gt=0)
    knowledge_scope_suggestion_model: str = Field(default="openai/gpt-5.6-terra", min_length=1)
    openrouter_allow_fallbacks: bool = True
    openrouter_provider_order: list[str] = Field(default_factory=list)
    max_parallel_lens_runs: int = Field(default=4, gt=0)
    lens_deadline_seconds: float = Field(default=300, gt=0)
    agent_trace_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=_REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def unique_prometheus_source_ids(self) -> Settings:
        source_ids = [source.id for source in self.prometheus_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("prometheus_sources must not contain duplicate IDs")
        return self

    @model_validator(mode="after")
    def validate_openrouter_routing(self) -> Settings:
        """Validate provider routing without requiring a model credential at startup."""
        if any(not provider.strip() for provider in self.openrouter_provider_order):
            raise ValueError("openrouter_provider_order must not contain blank providers")
        if len(self.openrouter_provider_order) != len(set(self.openrouter_provider_order)):
            raise ValueError("openrouter_provider_order must not contain duplicates")
        if not self.openrouter_allow_fallbacks and len(self.openrouter_provider_order) != 1:
            raise ValueError("disabled OpenRouter fallback requires exactly one provider")
        return self

    @model_validator(mode="after")
    def validate_agent_trace_mode(self) -> Settings:
        """Allow sensitive agent capture only in an explicitly development environment."""
        if self.agent_trace_enabled and self.app_env != "development":
            raise ValueError("agent_trace_enabled requires app_env=development")
        return self

    @property
    def agent_trace_root(self) -> Path:
        """Return the fixed ignored local root for sensitive agent trace artifacts."""
        return _REPOSITORY_ROOT / "tmp" / "agent-traces"

    def configured_secret_values(self) -> tuple[str, ...]:
        """Return configured secret values for local diagnostic redaction only."""
        values: list[str] = []
        values.extend(_database_password_values(self.database_url))
        if self.openrouter_api_key is not None:
            values.append(self.openrouter_api_key.get_secret_value())
        for source in self.prometheus_sources:
            credentials = source.credentials
            if isinstance(credentials, BearerTokenCredentials):
                values.append(credentials.token.get_secret_value())
            else:
                values.append(credentials.password.get_secret_value())
        return tuple(value for value in values if value)


def _database_password_values(database_url: str) -> tuple[str, ...]:
    """Extract a configured database password without retaining or logging its URL."""
    try:
        password = urlsplit(database_url).password
    except ValueError:
        return ()
    return (unquote(password),) if password else ()


@lru_cache
def get_settings() -> Settings:
    return Settings()
