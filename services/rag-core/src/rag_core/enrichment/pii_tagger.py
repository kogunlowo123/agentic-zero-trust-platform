"""PII detection, tagging, and optional redaction for corpus chunks."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import ClassVar

from rag_core.chunking.base import Chunk


@dataclass(frozen=True)
class _PIIPattern:
    name: str
    pattern: re.Pattern


_PATTERNS: list[_PIIPattern] = [
    _PIIPattern(
        name="email",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
    ),
    _PIIPattern(
        name="ipv4",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
    ),
    _PIIPattern(
        name="azure_subscription_id",
        pattern=re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
    ),
    _PIIPattern(
        name="phone_number",
        pattern=re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
    ),
]

_REDACT_PLACEHOLDER = "[REDACTED]"


class PIITagger:
    """Detects PII patterns in chunk content and records findings in metadata.

    When *redact* is ``True`` the returned chunks contain a copy of the content
    with matched spans replaced by ``[REDACTED]``.

    Args:
        redact: Whether to redact detected PII from the chunk content.
    """

    def __init__(self, redact: bool = False) -> None:
        self.redact = redact

    def tag(self, chunks: list[Chunk]) -> list[Chunk]:
        """Scan each chunk and annotate its metadata with PII findings.

        Args:
            chunks: Chunks to scan.

        Returns:
            List of chunks with ``has_pii`` and ``pii_types`` metadata fields
            set.  When *redact* is ``True`` the chunk content is replaced.
        """
        result: list[Chunk] = []
        for chunk in chunks:
            found_types: list[str] = []
            text = chunk.content

            for pattern_def in _PATTERNS:
                if pattern_def.pattern.search(text):
                    found_types.append(pattern_def.name)

            new_metadata = {
                **chunk.metadata,
                "has_pii": bool(found_types),
                "pii_types": found_types,
            }

            if self.redact and found_types:
                redacted_text = text
                for pattern_def in _PATTERNS:
                    redacted_text = pattern_def.pattern.sub(
                        _REDACT_PLACEHOLDER, redacted_text
                    )
                result.append(
                    Chunk(
                        content=redacted_text,
                        metadata=new_metadata,
                        chunk_id=chunk.chunk_id,
                        parent_doc_id=chunk.parent_doc_id,
                        position=chunk.position,
                    )
                )
            else:
                chunk.metadata.update(new_metadata)
                result.append(chunk)

        return result
