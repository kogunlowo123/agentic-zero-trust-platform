"""Auto-tagger for zero-trust domain corpus chunks."""

from __future__ import annotations

import re

from rag_core.chunking.base import Chunk

_ZERO_TRUST_KEYWORDS: list[str] = [
    "zero-trust",
    "zero trust",
    "opa",
    "policy",
    "posture",
    "jit",
    "svid",
    "spiffe",
    "nist",
    "identity",
    "authorization",
    "authentication",
    "least privilege",
    "micro-segmentation",
    "microsegmentation",
    "mTLS",
    "service mesh",
    "workload identity",
    "policy engine",
    "access control",
]

# Pre-compiled word-boundary patterns for faster repeated matching.
_COMPILED: list[tuple[str, re.Pattern]] = [
    (kw, re.compile(re.escape(kw), re.IGNORECASE))
    for kw in _ZERO_TRUST_KEYWORDS
]


class AutoTagger:
    """Tags chunks with zero-trust domain keywords and a relevance score.

    The zero-trust relevance score is the ratio of keyword occurrences to the
    total word count of the chunk, capped at ``1.0``.

    Added metadata fields:
    - ``tags``: list of matched keyword strings.
    - ``zero_trust_relevance_score``: float in ``[0.0, 1.0]``.
    """

    def tag(self, chunks: list[Chunk]) -> list[Chunk]:
        """Annotate each chunk with domain tags and a relevance score.

        Args:
            chunks: Chunks to tag.

        Returns:
            The same list with tagging metadata applied in-place.
        """
        for chunk in chunks:
            matched_keywords: list[str] = []
            total_hits = 0
            text = chunk.content
            word_count = max(len(text.split()), 1)

            for keyword, pattern in _COMPILED:
                hits = pattern.findall(text)
                if hits:
                    matched_keywords.append(keyword)
                    total_hits += len(hits)

            relevance_score = min(total_hits / word_count, 1.0)

            chunk.metadata["tags"] = matched_keywords
            chunk.metadata["zero_trust_relevance_score"] = relevance_score

        return chunks
