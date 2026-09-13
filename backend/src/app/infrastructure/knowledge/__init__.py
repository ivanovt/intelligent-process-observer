"""Infrastructure adapters for the curated knowledge corpus."""

from app.infrastructure.knowledge.retrieval import (
    CuratedKnowledgeReferenceResolver,
    CuratedKnowledgeRetriever,
    ResolvedCuratedKnowledgeReference,
    build_curated_knowledge_reference,
    parse_curated_knowledge_reference,
)

__all__ = [
    "CuratedKnowledgeReferenceResolver",
    "CuratedKnowledgeRetriever",
    "ResolvedCuratedKnowledgeReference",
    "build_curated_knowledge_reference",
    "parse_curated_knowledge_reference",
]
