"""Deterministic, bounded text extraction for retained PDF and Markdown sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class KnowledgeExtractionError(ValueError):
    """Report a safe extraction outcome without exposing source content."""


@dataclass(frozen=True, slots=True)
class ExtractedPassage:
    """One deterministic chunk candidate and its immutable source location."""

    text: str
    page_number: int | None
    page_ordinal: int | None
    heading_path: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class ExtractedKnowledgeDocument:
    """Normalized derived text and deterministic source-local chunk candidates."""

    text: str
    passages: tuple[ExtractedPassage, ...]


def extract_source(
    source_bytes: bytes, media_type: str, *, max_characters: int
) -> ExtractedKnowledgeDocument:
    """Extract bounded text from one already-admitted immutable source payload."""
    if media_type == "text/markdown":
        return _extract_markdown(source_bytes, max_characters=max_characters)
    if media_type == "application/pdf":
        return _extract_pdf(source_bytes, max_characters=max_characters)
    raise KnowledgeExtractionError("unsupported retained source media type")


def _extract_markdown(source_bytes: bytes, *, max_characters: int) -> ExtractedKnowledgeDocument:
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise KnowledgeExtractionError("markdown source is not valid UTF-8") from error
    normalized = _normalize_text(text)
    if not normalized:
        raise KnowledgeExtractionError("markdown source contains no extractable text")
    _require_limit(normalized, max_characters)
    headings: list[str] = []
    passages: list[ExtractedPassage] = []
    buffer: list[str] = []
    for line in normalized.splitlines():
        match = _MARKDOWN_HEADING.match(line)
        if match is not None:
            _append_markdown_passages(passages, buffer, tuple(headings))
            buffer = []
            level = len(match.group(1))
            title = match.group(2).strip()
            headings[level - 1 :] = [title]
        else:
            buffer.append(line)
    _append_markdown_passages(passages, buffer, tuple(headings))
    if not passages:
        passages.append(
            ExtractedPassage(
                text=normalized, page_number=None, page_ordinal=None, heading_path=None
            )
        )
    return ExtractedKnowledgeDocument(text=normalized, passages=tuple(passages))


def _append_markdown_passages(
    target: list[ExtractedPassage], lines: list[str], heading_path: tuple[str, ...]
) -> None:
    text = _normalize_text("\n".join(lines))
    if not text:
        return
    for piece in _split_text(text):
        target.append(
            ExtractedPassage(
                text=piece,
                page_number=None,
                page_ordinal=None,
                heading_path=heading_path or None,
            )
        )


def _extract_pdf(source_bytes: bytes, *, max_characters: int) -> ExtractedKnowledgeDocument:
    try:
        reader = PdfReader(BytesIO(source_bytes))
        page_texts = tuple(_normalize_text(page.extract_text() or "") for page in reader.pages)
    except Exception as error:
        raise KnowledgeExtractionError("PDF text extraction failed") from error
    text = _normalize_text("\n\n".join(page_texts))
    if not text:
        raise KnowledgeExtractionError("PDF source contains no extractable text")
    _require_limit(text, max_characters)
    passages: list[ExtractedPassage] = []
    for page_number, page_text in enumerate(page_texts, start=1):
        for page_ordinal, piece in enumerate(_split_text(page_text), start=1):
            passages.append(
                ExtractedPassage(
                    text=piece,
                    page_number=page_number,
                    page_ordinal=page_ordinal,
                    heading_path=None,
                )
            )
    if not passages:
        raise KnowledgeExtractionError("PDF source contains no extractable text")
    return ExtractedKnowledgeDocument(text=text, passages=tuple(passages))


_MAX_PASSAGE_UTF8_BYTES = 7_000


def _split_text(text: str, *, maximum_bytes: int = _MAX_PASSAGE_UTF8_BYTES) -> tuple[str, ...]:
    """Split text into UTF-8-safe passages that fit a whole retrieval item with its reference."""
    if len(text.encode("utf-8")) <= maximum_bytes:
        return (text,) if text else ()
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining.encode("utf-8")) <= maximum_bytes:
            chunks.append(remaining)
            break
        prefix = _utf8_prefix(remaining, maximum_bytes)
        cut = prefix.rfind(" ")
        if cut <= 0:
            cut = len(prefix)
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return tuple(chunk for chunk in chunks if chunk)


def _utf8_prefix(text: str, maximum_bytes: int) -> str:
    """Return the largest valid Unicode prefix whose UTF-8 bytes fit the requested bound."""
    payload = text.encode("utf-8")[:maximum_bytes]
    while payload:
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = payload[:-1]
    return ""


def _normalize_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).strip()


def _require_limit(text: str, max_characters: int) -> None:
    if len(text) > max_characters:
        raise KnowledgeExtractionError("extracted source exceeds the server limit")
