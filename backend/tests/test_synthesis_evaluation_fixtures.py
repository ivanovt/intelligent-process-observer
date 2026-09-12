"""Safety and coverage checks for bounded synthesis evaluation scenarios."""

from __future__ import annotations

import json

from synthesis_evaluation_fixtures import SYNTHESIS_EVALUATION_CASES


def test_synthesis_fixtures_cover_approved_representative_cases() -> None:
    """Keep the static scenarios aligned with the approved synthesis boundaries."""
    assert set(SYNTHESIS_EVALUATION_CASES) == {
        "direct_connectivity_with_auxiliary_logging",
        "conflicting_temporal_evidence",
        "symmetric_relative_change",
        "stable_only_findings",
        "material_limitations_with_findings",
        "forbidden_semantics",
    }

    direct = SYNTHESIS_EVALUATION_CASES["direct_connectivity_with_auxiliary_logging"]
    assert direct["relationship_evaluations"] == ()
    assert direct["expected"] == {
        "direct_and_auxiliary_are_separate": True,
        "direct_temporal_evidence_may_be_consolidated": True,
        "forbidden_cross_lens_claims": (
            "The logging spike caused the connectivity state.",
            "The logging spike confirms the connectivity state.",
            "The logging spike contradicts the connectivity state.",
        ),
    }

    comparison = SYNTHESIS_EVALUATION_CASES["symmetric_relative_change"]
    assert comparison["current_mean"] == 2.28
    assert comparison["reference_mean"] == 1.04
    assert comparison["relative_level_change"] == 0.7456
    assert comparison["forbidden_presentations"] == ("The current mean is 74.56% higher.",)

    assert SYNTHESIS_EVALUATION_CASES["stable_only_findings"]["expected_overall_state"] == (
        "no_significant_findings"
    )
    assert (
        SYNTHESIS_EVALUATION_CASES["material_limitations_with_findings"]["expected_overall_state"]
        == "uncertain"
    )


def test_synthesis_fixtures_are_evidence_safe_and_contain_no_sensitive_payloads() -> None:
    """Keep test scenarios free of provider input, credentials, and private trace content."""
    rendered = json.dumps(SYNTHESIS_EVALUATION_CASES).lower()
    forbidden_sensitive_terms = (
        "promql",
        "provider_query",
        "api_key",
        "password",
        "authorization",
        "cookie",
        "trace_payload",
        "agent-traces",
    )
    assert not any(term in rendered for term in forbidden_sensitive_terms)
