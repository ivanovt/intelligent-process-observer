"""Validate the narrow pre-invocation report-generation input boundary."""

from __future__ import annotations

from app.reporting.contracts import ReportGenerationRequest


def validate_request(value: ReportGenerationRequest) -> ReportGenerationRequest:
    """Require an exact immutable request with correlated Observation identities."""
    if not isinstance(value, ReportGenerationRequest):
        raise ValueError("report generation requires a ReportGenerationRequest")
    if value.context.identity != value.analysis_result.identity:
        raise ValueError("report context identity must match analysis result identity")
    return value
