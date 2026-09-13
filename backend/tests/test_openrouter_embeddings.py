"""Focused tests for private OpenRouter curated-knowledge embeddings."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.settings import Settings
from app.infrastructure.openrouter.embeddings import (
    OpenRouterEmbeddingAdapter,
    OpenRouterEmbeddingError,
    OpenRouterEmbeddingUnavailableError,
)


def _adapter(
    handler: httpx.MockTransport | None = None,
    **settings_values: object,
) -> OpenRouterEmbeddingAdapter:
    settings = Settings(openrouter_api_key="embedding-test-secret", **settings_values)
    if handler is None:
        return OpenRouterEmbeddingAdapter(settings)
    return OpenRouterEmbeddingAdapter(
        settings,
        client_factory=lambda: httpx.AsyncClient(transport=handler),
    )


def _embedding(value: float, *, dimensions: int = 1_536) -> list[float]:
    return [value] * dimensions


def test_document_embeddings_are_batched_and_preserve_input_order() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        batch = requests[-1]["input"]
        assert isinstance(batch, list)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": _embedding(float(index + len(requests)))}
                    for index in reversed(range(len(batch)))
                ]
            },
        )

    adapter = _adapter(httpx.MockTransport(handler), knowledge_embedding_batch_size=2)
    result = asyncio.run(adapter.embed_documents(("first", "second", "third")))

    assert [request["input"] for request in requests] == [["first", "second"], ["third"]]
    assert all(request["model"] == "openai/text-embedding-3-small" for request in requests)
    assert all(request["dimensions"] == 1_536 for request in requests)
    assert all(request["input_type"] == "search_document" for request in requests)
    assert [vector[0] for vector in result] == [1.0, 2.0, 2.0]
    assert all(len(vector) == 1_536 for vector in result)


def test_query_embedding_uses_only_the_admitted_query_text() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": _embedding(0.25)}]})

    query = "Finding finding-17: dependency timeout"
    result = asyncio.run(_adapter(httpx.MockTransport(handler)).embed_query(query))

    assert result[0] == 0.25
    assert json.loads(seen[0].content)["input"] == [query]
    assert json.loads(seen[0].content)["input_type"] == "search_query"


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": _embedding(1, dimensions=1_535)}]},
        {
            "data": [
                {"index": 0, "embedding": _embedding(1)},
                {"index": 0, "embedding": _embedding(1)},
            ]
        },
        {"data": [{"index": 1, "embedding": _embedding(1)}]},
        {"data": []},
    ],
)
def test_invalid_embedding_dimension_or_response_is_rejected_without_provider_detail(
    payload: dict[str, object],
) -> None:
    adapter = _adapter(httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))

    with pytest.raises(OpenRouterEmbeddingError) as error:
        asyncio.run(adapter.embed_query("valid grounded query"))

    assert str(error.value) == "embedding_response_invalid"


def test_non_finite_embedding_values_are_rejected() -> None:
    non_finite_embedding = "[NaN," + ",".join("0" for _ in range(1_535)) + "]"
    response = httpx.Response(
        200,
        content=('{"data":[{"index":0,"embedding":' + non_finite_embedding + "}]}").encode(),
        headers={"Content-Type": "application/json"},
    )
    adapter = _adapter(httpx.MockTransport(lambda _: response))

    with pytest.raises(OpenRouterEmbeddingError) as error:
        asyncio.run(adapter.embed_query("valid grounded query"))

    assert str(error.value) == "embedding_response_invalid"


def test_provider_failure_is_redacted() -> None:
    secret = "embedding-test-secret"
    source_text = "approved process guide confidential sentence"
    adapter = _adapter(
        httpx.MockTransport(
            lambda _: httpx.Response(503, text=f"provider body includes {secret} and {source_text}")
        )
    )

    with pytest.raises(OpenRouterEmbeddingError) as error:
        asyncio.run(adapter.embed_documents((source_text,)))

    rendered = str(error.value)
    assert rendered == "embedding_request_failed"
    assert secret not in rendered
    assert source_text not in rendered


def test_missing_credential_does_not_prevent_startup_and_fails_safely_on_use() -> None:
    adapter = OpenRouterEmbeddingAdapter(Settings(openrouter_api_key=None))

    assert adapter.is_available is False
    with pytest.raises(OpenRouterEmbeddingUnavailableError) as error:
        asyncio.run(adapter.embed_documents(("approved extracted text",)))
    assert str(error.value) == "embedding_service_unavailable"


def test_empty_document_batch_never_calls_provider() -> None:
    adapter = OpenRouterEmbeddingAdapter(Settings(openrouter_api_key=None))

    assert asyncio.run(adapter.embed_documents(())) == ()
