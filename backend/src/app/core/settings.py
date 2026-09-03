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


@lru_cache
def get_settings() -> Settings:
    return Settings()
