"""Focused regression tests for Observation reasoning evidence projection."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.reasoning.catalog import build_catalog


def test_alert_catalog_excludes_provider_source_metadata() -> None:
    """Provider-native source fields cannot become citeable finding evidence."""
    lens_run_id = uuid4()
    alert = SimpleNamespace(
        lens_type="alert",
        identity=SimpleNamespace(lens_run_id=lens_run_id),
        model_dump=lambda mode: {
            "alerts": [
                {
                    "id": "alert-1",
                    "source_ref": "provider://private",
                    "status": {"normalized": "active", "source": "provider-status"},
                }
            ],
            "alert_activity": {"record_count": 1},
            "status_distribution": {"active": 1},
            "overall_importance": "high",
        },
    )
    value = SimpleNamespace(usable_results=(alert,), relationships=())

    catalog = build_catalog(value)

    locators = {entry.reference.locator for entry in catalog}
    assert ("alerts", 0, "id") in locators
    assert ("alerts", 0, "source_ref") not in locators
    assert ("alerts", 0, "status", "source") not in locators
