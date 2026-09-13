"""Regression coverage for Alembic's interaction with application logging."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.settings import get_settings

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_config() -> Generator[Config]:
    """Provide an Alembic config against the explicitly configured PostgreSQL test database."""
    database_url = os.environ.get("IPO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set IPO_TEST_DATABASE_URL to run PostgreSQL integration tests")

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    yield config
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url
    get_settings.cache_clear()


def test_alembic_configuration_keeps_existing_operational_logger_enabled(
    alembic_config: Config,
) -> None:
    """Migration logging must not disable an application logger created by earlier tests."""
    logger = logging.getLogger("app.operational")
    previous_disabled = logger.disabled
    logger.disabled = False
    try:
        command.upgrade(alembic_config, "head")
        assert logger.disabled is False
    finally:
        logger.disabled = previous_disabled
