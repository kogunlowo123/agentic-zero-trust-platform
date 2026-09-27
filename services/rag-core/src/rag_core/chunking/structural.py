"""Structural chunker for policy and framework documents.

Splits text on Markdown headings (``#``, ``##``, ``###``) and numbered
section headers such as ``1.``, ``2.3``, ``3.4.1``.  The section hierarchy
is recorded in chunk metadata as ``section_path``.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from rag_core.chunking.base import BaseChunker, Chunk


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Matches Markdown ATX headings: ``# Title``, ``## Title``, ``### Title``
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Matches numbered sections: ``1.``, ``2.3``, ``3.4.1`` at the start of a line
_NUM_SECTION = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.+)$", re.MULTILINE)


class _SectionNode:
    """Temporary node used while building the hierarchy."""

    def __init__(
        self,
        title: str,
        level: int,
        path: list[str],
        start: int,
    ) -> None:
        self.title = title
        self.level = level
        self.path = path
        self.start = start


def _build_section_paths(text: str) -> list[tuple[int, list[str], str]]:
    """Return a list of ``(char_offset, section_path, section_title)`` tuples.

    Boundaries are derived from both Markdown headings and numbered sections.
    """
    events: list[tuple[int, int, str, str]] = []  # (offset, level, path_component, title)

    for m in _MD_HEADING.finditer(text):
        level = len(m.group(1))
        title = m.group(2).strip()
        events.append((m.start(), level, title, title))

    for m in _NUM_SECTION.finditer(text):
        # Use dot-count to determine depth, e.g. "3.4.1" → depth 3
        num_str = m.group(1).rstrip(".")
        level = num_str.count(".") + 1 + 6  # offset beyond heading levels
        title = m.group(2).strip()
        section_num = m.group(1)
        events.append((m.start(), level, section_num, title))

    events.sort(key=lambda e: e[0])

    # Build running path stack
    stack: list[tuple[int, str]] = []  # (level, component)
    result: list[tuple[int, list[str], str]] = []

    for offset, level, component, title in events:
        # Pop stack entries at the same or deeper level
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, component))
        result.append((offset, [c for _, c in stack], title))

    return result


class StructuralChunker(BaseChunker):
    """Chunks policy documents based on their structural section markers.

    Splits on Markdown headings and numbered sections.  The resulting chunks
    carry ``section_path`` and ``section_title`` metadata.

    Args:
        min_chunk_size: Sections shorter than this (in characters) are merged
            with their predecessor.
    """

    def __init__(self, min_chunk_size: int = 128) -> None:
        self.min_chunk_size = min_chunk_size

    def chunk(self, documents: list) -> list[Chunk]:  # type: ignore[override]
        all_chunks: list[Chunk] = []
        for doc in documents:
            parent_id = _sha256(doc.content[:256])
            all_chunks.extend(self._chunk_document(doc, parent_id))
        return all_chunks

    def _chunk_document(self, doc, parent_id: str) -> list[Chunk]:
        text = doc.content
        boundaries = _build_section_paths(text)

        if not boundaries:
            # No headings found — return whole document as a single chunk.
            return [
                Chunk(
                    content=text.strip(),
                    metadata={**doc.metadata, "section_path": [], "section_title": ""},
                    chunk_id=_sha256(text),
                    parent_doc_id=parent_id,
                    position=0,
                )
            ]

        # Build (start, end, section_path, section_title) tuples
        sections: list[tuple[int, int, list[str], str]] = []
        for i, (offset, path, title) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            sections.append((offset, end, path, title))

        # Prepend any text that precedes the first heading.
        preamble = text[: boundaries[0][0]].strip()

        raw_pieces: list[dict[str, Any]] = []
        if preamble:
            raw_pieces.append(
                {"content": preamble, "section_path": [], "section_title": "preamble"}
            )
        for start, end, path, title in sections:
            content = text[start:end].strip()
            if content:
                raw_pieces.append(
                    {"content": content, "section_path": path, "section_title": title}
                )

        # Merge short pieces
        merged: list[dict[str, Any]] = []
        for piece in raw_pieces:
            if merged and len(piece["content"]) < self.min_chunk_size:
                merged[-1]["content"] += "\n\n" + piece["content"]
            else:
                merged.append(piece)

        chunks: list[Chunk] = []
        for position, piece in enumerate(merged):
            content = piece["content"]
            metadata: dict[str, Any] = {
                **doc.metadata,
                "section_path": piece["section_path"],
                "section_title": piece["section_title"],
            }
            chunks.append(
                Chunk(
                    content=content,
                    metadata=metadata,
                    chunk_id=_sha256(content),
                    parent_doc_id=parent_id,
                    position=position,
                )
            )
        return chunks
