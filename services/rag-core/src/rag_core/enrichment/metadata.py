"""Metadata enrichment: timestamps, word counts, language, and document type."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from rag_core.chunking.base import Chunk

# Heuristic keyword sets for document-type classification.
_POLICY_SIGNALS = {
    "policy", "policies", "compliance", "nist", "sp 800", "control", "requirement",
    "regulation", "framework", "guideline", "standard", "mandate",
}
_FRAMEWORK_SIGNALS = {
    "framework", "architecture", "zero trust", "zta", "spiffe", "svid", "opa",
    "posture", "mesh", "istio",
}
_TECHNICAL_SIGNALS = {
    "api", "config", "deployment", "dockerfile", "yaml", "json", "code", "sdk",
    "library", "function", "class", "interface",
}


def _infer_doc_type(metadata: dict[str, Any]) -> str:
    source: str = str(metadata.get("source_file", "")).lower()
    heading: str = str(metadata.get("headings", "")).lower()
    combined = source + " " + heading

    if any(kw in combined for kw in _POLICY_SIGNALS):
        return "policy"
    if any(kw in combined for kw in _FRAMEWORK_SIGNALS):
        return "framework"
    if any(kw in combined for kw in _TECHNICAL_SIGNALS):
        return "technical"
    return "policy"  # Safe default for zero-trust corpus


def _detect_language(text: str) -> str:
    try:
        from langdetect import detect, LangDetectException

        return detect(text)
    except Exception:
        return "en"


class MetadataEnricher:
    """Enriches a list of chunks with standard metadata fields.

    Added / overwritten fields:
    - ``ingestion_timestamp``: ISO-8601 UTC timestamp of enrichment.
    - ``word_count``: Number of whitespace-delimited tokens in the chunk content.
    - ``language``: ISO-639-1 language code detected by *langdetect*.
    - ``doc_type``: One of ``"policy"``, ``"framework"``, ``"technical"``.
    """

    def enrich(self, chunks: list[Chunk]) -> list[Chunk]:
        """Enrich each chunk in-place and return the same list.

        Args:
            chunks: Chunks to enrich.

        Returns:
            The same list with metadata fields added.
        """
        now = datetime.now(tz=timezone.utc).isoformat()
        for chunk in chunks:
            chunk.metadata["ingestion_timestamp"] = now
            chunk.metadata["word_count"] = len(chunk.content.split())
            chunk.metadata["language"] = _detect_language(chunk.content)
            chunk.metadata["doc_type"] = _infer_doc_type(chunk.metadata)
        return chunks
