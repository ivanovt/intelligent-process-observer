"""Focused API and source-chunk tests for curated Knowledge Administration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from starlette.requests import Request

from app.knowledge import api as knowledge_api
from app.knowledge.api import _bounded_body, _parse_multipart, get_ingestion_service, get_session
from app.knowledge.extraction import KnowledgeExtractionError, extract_source
from app.knowledge.ingestion import KnowledgeUploadRejected
from app.main import app

_DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")


class StubIngestionService:
    """Capture admitted upload candidates without invoking persistence or extraction."""

    def __init__(self) -> None:
        self.candidate = None
        self.max_upload_bytes = 10 * 1024

    async def create_document(self, candidate):
        """Record the first immutable source candidate and return a stable identity."""
        self.candidate = candidate
        return _DOCUMENT_ID, 1


class StubRepository:
    """Expose only the inert retained projections needed by isolated HTTP tests."""

    async def get_document(self, _session, _document_id):
        """Return a single retained imported Markdown version."""
        tag = SimpleNamespace(service_id="cooling-loop", aliases=["cooling"], supported_versions=[])
        version = SimpleNamespace(
            version=1,
            title="Cooling guide",
            document_type="runbook",
            authority="internal_approved",
            owner="operations",
            source_reference=None,
            source_media_type="text/markdown",
            content_hash="a" * 64,
            extraction_state="ready",
            lifecycle="imported",
            service_tags=[tag],
        )
        return SimpleNamespace(id=_DOCUMENT_ID, versions=[version])

    async def get_version(self, _session, _document_id, _version):
        """Return exact bytes for safe attachment testing."""
        return SimpleNamespace(source_media_type="text/markdown", source_bytes=b"# retained\r\n")


async def _session() -> AsyncIterator[object]:
    """Yield a no-op request session for isolated route projection tests."""
    yield object()


def test_markdown_source_passages_are_utf8_bounded_and_heading_local() -> None:
    """Every derived Markdown passage fits the whole-item budget and keeps its heading path."""
    source = ("# Operations\n## Cooling\n" + "ж" * 4_000).encode()

    extracted = extract_source(source, "text/markdown", max_characters=10_000)

    assert len(extracted.passages) >= 2
    assert all(len(item.text.encode("utf-8")) <= 7_000 for item in extracted.passages)
    assert all(item.heading_path == ("Operations", "Cooling") for item in extracted.passages)
    assert all(
        item.page_number is None and item.page_ordinal is None for item in extracted.passages
    )


def test_pdf_passages_reset_page_local_ordinals(monkeypatch) -> None:
    """PDF chunk locations retain page-local numbering independent of global chunk order."""

    class Page:
        """Return fixed textual content for one fake PDF page."""

        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            """Return the fixture's page text."""
            return self.text

    class Reader:
        """Expose two PDF pages without requiring fixture binary construction."""

        pages = [Page("first " * 2_000), Page("second")]

    monkeypatch.setattr("app.knowledge.extraction.PdfReader", lambda _: Reader())
    extracted = extract_source(b"%PDF-fake", "application/pdf", max_characters=100_000)

    assert [item.page_ordinal for item in extracted.passages if item.page_number == 1] == [1, 2]
    assert [item.page_ordinal for item in extracted.passages if item.page_number == 2] == [1]


def test_extraction_rejects_empty_derived_markdown_text() -> None:
    """Whitespace-only retained text cannot become a ready extraction or indexed passage."""
    with pytest.raises(KnowledgeExtractionError, match="no extractable text"):
        extract_source(b"\r\n \t\r\n", "text/markdown", max_characters=100)


def test_upload_retains_exact_trailing_source_bytes_and_source_download_is_inert(
    monkeypatch,
) -> None:
    """The fixed multipart parser preserves source bytes and downloads always force attachment."""
    ingestion = StubIngestionService()

    async def service() -> StubIngestionService:
        return ingestion

    monkeypatch.setattr(knowledge_api, "KnowledgeRepository", StubRepository)
    app.dependency_overrides[get_ingestion_service] = service
    app.dependency_overrides[get_session] = _session

    async def scenario() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            upload = await client.post(
                "/api/v1/knowledge/documents",
                data={
                    "metadata": (
                        '{"title":"Cooling guide","document_type":"runbook",'
                        '"authority":"internal_approved","owner":"operations",'
                        '"service_tags":[]}'
                    )
                },
                files={"file": ("guide.md", b"# retained\r\n", "text/markdown")},
            )
            source = await client.get(
                f"/api/v1/knowledge/documents/{_DOCUMENT_ID}/versions/1/source"
            )
            return upload, source

    try:
        upload, source = asyncio.run(scenario())
    finally:
        app.dependency_overrides.clear()

    assert upload.status_code == 200
    assert upload.json()["versions"][0]["media_type"] == "text/markdown"
    assert upload.json()["versions"][0]["lifecycle_state"] == "imported"
    assert ingestion.candidate.source_bytes == b"# retained\r\n"
    assert source.status_code == 200 and source.content == b"# retained\r\n"
    assert source.headers["content-type"] == "application/octet-stream"
    assert source.headers["x-content-type-options"] == "nosniff"
    assert source.headers["content-disposition"].startswith("attachment;")


def test_delimiter_aware_parser_retains_embedded_boundary_like_pdf_bytes() -> None:
    """Only a complete delimiter line separates MIME parts from retained binary source bytes."""
    boundary = b"fixed-boundary"
    source = b"%PDF-1.7\r\n--fixed-boundary-not-a-delimiter\r\nbinary-tail\r\n"
    payload = (
        b"--fixed-boundary\r\n"
        b'Content-Disposition: form-data; name="metadata"\r\n\r\n'
        b"{}\r\n"
        b"--fixed-boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="guide.pdf"\r\n'
        b"Content-Type: application/pdf\r\n\r\n" + source + b"\r\n--fixed-boundary--\r\n"
    )

    fields = _parse_multipart(payload, boundary)

    assert fields["file"][1] == source


def test_bounded_body_rejects_oversized_multipart_before_full_allocation() -> None:
    """The streaming reader stops when framing plus source exceeds the bounded intake cap."""
    chunks = iter((b"x" * 40_000, b"y" * 40_000))

    async def receive() -> dict[str, object]:
        try:
            return {"type": "http.request", "body": next(chunks), "more_body": True}
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "method": "POST", "headers": []}, receive)

    with pytest.raises(KnowledgeUploadRejected, match="exceeds"):
        asyncio.run(_bounded_body(request, max_upload_bytes=10))
