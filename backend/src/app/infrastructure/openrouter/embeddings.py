"""Private OpenRouter embedding adapter for curated knowledge."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import httpx

from app.core.settings import Settings

_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
_TIMEOUT_STATUS_CODES = frozenset((httpx.codes.REQUEST_TIMEOUT, 524))
_ClientFactory = Callable[[], httpx.AsyncClient]


class OpenRouterEmbeddingError(RuntimeError):
    """Safe failure raised when OpenRouter embeddings cannot be used."""


class OpenRouterEmbeddingUnavailableError(OpenRouterEmbeddingError):
    """Safe failure raised when no server-side OpenRouter credential is configured."""


class OpenRouterEmbeddingAdapter:
    """Create validated OpenRouter embeddings for approved knowledge text only."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: _ClientFactory | None = None,
    ) -> None:
        """Bind the adapter to server-only settings without requiring a credential at startup."""
        self._settings = settings
        self._client_factory = client_factory or self._new_client

    @property
    def is_available(self) -> bool:
        """Report whether a non-blank server-only credential is currently configured."""
        return self._settings.openrouter_api_key is not None and bool(
            self._settings.openrouter_api_key.get_secret_value().strip()
        )

    async def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Embed extracted approved document chunks in configured bounded batches."""
        return await self._embed_batched(texts, input_type="search_document")

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed one admitted finding-grounded retrieval query."""
        embeddings = await self._embed_batched((text,), input_type="search_query")
        return embeddings[0]

    async def _embed_batched(
        self,
        texts: Sequence[str],
        *,
        input_type: str,
    ) -> tuple[tuple[float, ...], ...]:
        normalized = tuple(texts)
        if not normalized:
            return ()
        if any(not isinstance(text, str) or not text.strip() for text in normalized):
            raise ValueError("embedding input must contain only non-blank text")
        if not self.is_available:
            raise OpenRouterEmbeddingUnavailableError("embedding_service_unavailable")

        result: list[tuple[float, ...]] = []
        for start in range(0, len(normalized), self._settings.knowledge_embedding_batch_size):
            result.extend(
                await self._embed_batch(
                    normalized[start : start + self._settings.knowledge_embedding_batch_size],
                    input_type=input_type,
                )
            )
        return tuple(result)

    async def _embed_batch(
        self,
        texts: tuple[str, ...],
        *,
        input_type: str,
    ) -> tuple[tuple[float, ...], ...]:
        credential = self._settings.openrouter_api_key
        if credential is None:
            raise OpenRouterEmbeddingUnavailableError("embedding_service_unavailable")

        try:
            async with self._client_factory() as client:
                response = await client.post(
                    _EMBEDDINGS_URL,
                    headers={"Authorization": f"Bearer {credential.get_secret_value()}"},
                    json={
                        "model": self._settings.knowledge_embedding_model,
                        "input": list(texts),
                        "dimensions": self._settings.knowledge_embedding_dimensions,
                        "input_type": input_type,
                    },
                )
                if response.status_code in _TIMEOUT_STATUS_CODES:
                    raise TimeoutError("embedding_request_timed_out")
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise TimeoutError("embedding_request_timed_out") from error
        except httpx.HTTPError as error:
            raise OpenRouterEmbeddingError("embedding_request_failed") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise OpenRouterEmbeddingError("embedding_response_invalid") from error
        return _parse_embeddings(
            payload,
            expected_count=len(texts),
            dimensions=self._settings.knowledge_embedding_dimensions,
        )

    def _new_client(self) -> httpx.AsyncClient:
        """Create a bounded private HTTP client for one embedding request."""
        return httpx.AsyncClient(timeout=self._settings.knowledge_retrieval_timeout_seconds)


def _parse_embeddings(
    payload: object,
    *,
    expected_count: int,
    dimensions: int,
) -> tuple[tuple[float, ...], ...]:
    """Validate and restore provider embeddings to the caller's input order."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise OpenRouterEmbeddingError("embedding_response_invalid")
    records = payload["data"]
    if len(records) != expected_count:
        raise OpenRouterEmbeddingError("embedding_response_invalid")

    ordered: list[tuple[float, ...] | None] = [None] * expected_count
    for record in records:
        if not isinstance(record, dict):
            raise OpenRouterEmbeddingError("embedding_response_invalid")
        index = record.get("index")
        embedding = record.get("embedding")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= expected_count
            or ordered[index] is not None
            or not isinstance(embedding, list)
            or len(embedding) != dimensions
        ):
            raise OpenRouterEmbeddingError("embedding_response_invalid")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in embedding
        ):
            raise OpenRouterEmbeddingError("embedding_response_invalid")
        ordered[index] = tuple(float(value) for value in embedding)

    if any(vector is None for vector in ordered):
        raise OpenRouterEmbeddingError("embedding_response_invalid")
    return tuple(vector for vector in ordered if vector is not None)
