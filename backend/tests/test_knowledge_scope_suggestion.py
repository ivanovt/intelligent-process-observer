"""Boundary tests for advisory catalog-backed knowledge scope suggestions."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.core.settings import Settings
from app.infrastructure.agents.pydantic_ai_knowledge_scope import (
    KnowledgeScopeSuggestionPolicyViolation,
    PydanticAIKnowledgeScopeSuggestionAgent,
)
from app.infrastructure.openrouter.composition import (
    build_knowledge_scope_suggestion_agent,
    build_knowledge_scope_suggestion_model,
)
from app.knowledge.api import get_scope_suggestion_service, get_session
from app.knowledge.management_contracts import ApprovedServiceCatalogEntry
from app.knowledge.scope_suggestion import (
    KnowledgeScopeSuggestionDraft,
    KnowledgeScopeSuggestionLens,
    KnowledgeScopeSuggestionModelRequest,
    KnowledgeScopeSuggestionResponse,
    KnowledgeScopeSuggestionService,
)
from app.main import app


def _run(coroutine):
    """Run one async unit under an isolated event loop."""
    return asyncio.run(coroutine)


def _draft() -> KnowledgeScopeSuggestionDraft:
    """Build the smallest semantic draft used by suggestion tests."""
    return KnowledgeScopeSuggestionDraft(
        name="Cooling health",
        description="Monitors the chilled-water system.",
        objective="Detect abnormal cooling behavior.",
        lenses=[
            KnowledgeScopeSuggestionLens(
                name="Chiller pressure", description="Tracks primary chiller pressure."
            ),
        ],
    )


def _catalog() -> tuple[ApprovedServiceCatalogEntry, ...]:
    """Build one approved catalog projection without document content."""
    return (
        ApprovedServiceCatalogEntry(service_id="mprm-server", aliases=("management-server",)),
        ApprovedServiceCatalogEntry(service_id="cooling-plant", aliases=("chiller",)),
    )


def _collision_catalog() -> tuple[ApprovedServiceCatalogEntry, ...]:
    """Build a catalog whose shared alias must remain unresolved."""
    return (
        ApprovedServiceCatalogEntry(
            service_id="cooling-primary", aliases=("cooling", "primary-chiller")
        ),
        ApprovedServiceCatalogEntry(
            service_id="cooling-backup", aliases=("cooling", "backup-chiller")
        ),
    )


class StubCatalog:
    """Record catalog reads without persistence mutation."""

    def __init__(self, catalog: tuple[ApprovedServiceCatalogEntry, ...] = ()) -> None:
        self.catalog = catalog
        self.calls = 0

    async def approved_service_catalog(self, _session):
        """Return the configured catalog projection."""
        self.calls += 1
        return self.catalog


class StubAgent:
    """Return one fixed completion or raise the configured model failure."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.requests: list[KnowledgeScopeSuggestionModelRequest] = []

    async def suggest(self, request: KnowledgeScopeSuggestionModelRequest):
        """Record only the typed corpus-blind model projection."""
        self.requests.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_service_returns_only_catalog_backed_ids_without_persistence() -> None:
    """A valid completion is projected as a catalog subset and only reads the catalog."""
    catalog = StubCatalog(_catalog())
    agent = StubAgent(KnowledgeScopeSuggestionResponse(service_ids=("cooling-plant",)))
    service = KnowledgeScopeSuggestionService(catalog, lambda: agent)

    response = _run(service.suggest(None, _draft()))

    assert response == KnowledgeScopeSuggestionResponse(service_ids=("cooling-plant",))
    assert catalog.calls == 1
    assert agent.requests == [
        KnowledgeScopeSuggestionModelRequest(draft=_draft(), catalog=_catalog())
    ]


@pytest.mark.parametrize(
    "result",
    [
        KnowledgeScopeSuggestionResponse(service_ids=("invented-service",)),
        RuntimeError("provider details must not escape"),
        object(),
    ],
)
def test_service_returns_safe_empty_response_for_invalid_or_unavailable_work(
    result: object,
) -> None:
    """Invalid model output and model failures cannot expose details or mutate a scope."""
    service = KnowledgeScopeSuggestionService(StubCatalog(_catalog()), lambda: StubAgent(result))

    assert _run(service.suggest(None, _draft())) == KnowledgeScopeSuggestionResponse()


def test_service_skips_model_composition_when_the_approved_catalog_is_empty() -> None:
    """An empty catalog returns no suggestion without creating an LLM adapter."""
    factory_calls = 0

    def agent_factory() -> StubAgent:
        nonlocal factory_calls
        factory_calls += 1
        return StubAgent(KnowledgeScopeSuggestionResponse())

    response = _run(
        KnowledgeScopeSuggestionService(StubCatalog(), agent_factory).suggest(None, _draft())
    )

    assert response == KnowledgeScopeSuggestionResponse()
    assert factory_calls == 0


def test_service_rejects_a_service_selected_only_from_a_shared_alias() -> None:
    """A shared catalog alias cannot silently resolve to either owning service."""
    draft = KnowledgeScopeSuggestionDraft(
        name="Cooling health",
        description=None,
        objective="Observe cooling behavior.",
        lenses=[],
    )
    service = KnowledgeScopeSuggestionService(
        StubCatalog(_collision_catalog()),
        lambda: StubAgent(KnowledgeScopeSuggestionResponse(service_ids=("cooling-primary",))),
    )

    assert _run(service.suggest(None, draft)) == KnowledgeScopeSuggestionResponse()


def test_service_keeps_a_semantic_catalog_suggestion_without_a_literal_catalog_term() -> None:
    """A model may select a catalog ID from draft semantics when no shared alias is present."""
    draft = KnowledgeScopeSuggestionDraft(
        name="Hydronic loop health",
        description="Monitor the plant water circulation.",
        objective="Detect pressure instability in the chilled-water circuit.",
        lenses=[],
    )
    service = KnowledgeScopeSuggestionService(
        StubCatalog(_collision_catalog()),
        lambda: StubAgent(KnowledgeScopeSuggestionResponse(service_ids=("cooling-primary",))),
    )

    assert _run(service.suggest(None, draft)) == KnowledgeScopeSuggestionResponse(
        service_ids=("cooling-primary",)
    )


@pytest.mark.parametrize(
    ("draft_name", "expected_service_id"),
    [
        ("Cooling-primary health", "cooling-primary"),
        ("Primary-chiller health", "cooling-primary"),
    ],
)
def test_service_preserves_explicit_canonical_and_unique_alias_suggestions(
    draft_name: str,
    expected_service_id: str,
) -> None:
    """Canonical service IDs and aliases with one owner remain valid suggestion evidence."""
    draft = KnowledgeScopeSuggestionDraft(
        name=draft_name,
        description=None,
        objective="Observe component behavior.",
        lenses=[],
    )
    service = KnowledgeScopeSuggestionService(
        StubCatalog(_collision_catalog()),
        lambda: StubAgent(KnowledgeScopeSuggestionResponse(service_ids=(expected_service_id,))),
    )

    assert _run(service.suggest(None, draft)) == KnowledgeScopeSuggestionResponse(
        service_ids=(expected_service_id,)
    )


def test_pydantic_adapter_exposes_only_draft_and_catalog_to_one_no_tool_request() -> None:
    """The model receives the approved projection once, with no registered function tools."""
    calls: list[tuple[object, AgentInfo]] = []

    def scripted(messages, info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"service_ids": ["cooling-plant"]})]
        )

    request = KnowledgeScopeSuggestionModelRequest(draft=_draft(), catalog=_catalog())
    response = _run(
        PydanticAIKnowledgeScopeSuggestionAgent(FunctionModel(scripted)).suggest(request)
    )

    assert response == KnowledgeScopeSuggestionResponse(service_ids=("cooling-plant",))
    assert len(calls) == 1
    messages, info = calls[0]
    assert not info.function_tools
    prompt = next(
        part.content
        for message in messages
        for part in message.parts
        if part.part_kind == "user-prompt"
    )
    assert json.loads(prompt) == request.model_dump(mode="json")
    assert "document" not in prompt and "provider" not in prompt and "chunk" not in prompt


def test_pydantic_adapter_rejects_an_invented_catalog_id() -> None:
    """The adapter treats an ID outside its supplied catalog as a policy violation."""

    def scripted(_messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"service_ids": ["invented-service"]})]
        )

    request = KnowledgeScopeSuggestionModelRequest(draft=_draft(), catalog=_catalog())
    with pytest.raises(KnowledgeScopeSuggestionPolicyViolation):
        _run(PydanticAIKnowledgeScopeSuggestionAgent(FunctionModel(scripted)).suggest(request))


def test_openrouter_composition_uses_the_separate_suggestion_model_and_no_retries() -> None:
    """The private adapter reuses the credential and routing policy without transport retries."""
    settings = Settings(
        openrouter_api_key="scope-suggestion-credential",
        knowledge_scope_suggestion_model="vendor/suggestion-model",
        openrouter_request_timeout_seconds=43.5,
        observation_reasoning_max_output_tokens=765,
        openrouter_allow_fallbacks=False,
        openrouter_provider_order=["pinned"],
    )

    model = build_knowledge_scope_suggestion_model(settings)
    agent = build_knowledge_scope_suggestion_agent(settings)

    assert model.model_name == "vendor/suggestion-model"
    assert model.settings == {
        "extra_body": {"provider": {"allow_fallbacks": False, "order": ["pinned"]}}
    }
    assert model.provider.client.max_retries == 0
    assert agent._settings == {"timeout": 43.5, "max_tokens": 765}


@pytest.mark.parametrize("key", [None, " "])
def test_openrouter_scope_suggestion_composition_requires_a_nonblank_secret(
    key: str | None,
) -> None:
    """Missing credentials become a safe service outcome without leaking secret material."""
    with pytest.raises(ValueError) as error:
        build_knowledge_scope_suggestion_model(Settings(openrouter_api_key=key))
    assert "credential" in str(error.value).lower()


def test_scope_suggestion_model_setting_is_nonblank() -> None:
    """The separate server-only model setting rejects an invalid empty value."""
    with pytest.raises(ValidationError):
        Settings(knowledge_scope_suggestion_model="")


async def _no_session():
    yield None


def test_api_returns_a_diagnostic_free_empty_suggestion_for_an_unavailable_model() -> None:
    """The public API exposes only the empty response contract for model unavailability."""
    service = KnowledgeScopeSuggestionService(
        StubCatalog(_catalog()), lambda: StubAgent(RuntimeError("secret provider failure"))
    )

    async def stub_service() -> KnowledgeScopeSuggestionService:
        return service

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/knowledge/scope-suggestion",
                json={
                    "name": "Cooling health",
                    "description": None,
                    "objective": "Detect abnormal cooling behavior.",
                    "lenses": [{"name": "Chiller pressure", "description": None}],
                },
            )

    app.dependency_overrides[get_session] = _no_session
    app.dependency_overrides[get_scope_suggestion_service] = stub_service
    try:
        response = _run(send())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"service_ids": []}
