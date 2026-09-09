from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

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
    openrouter_allow_fallbacks: bool = True
    openrouter_provider_order: list[str] = Field(default_factory=list)
    max_parallel_lens_runs: int = Field(default=4, gt=0)
    lens_deadline_seconds: float = Field(default=300, gt=0)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
