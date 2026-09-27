"""Citation accuracy: verify cited doc IDs exist in source docs."""
from __future__ import annotations
import re


def extract_citations(response: str) -> list[str]:
    return re.findall(r'\[DOC-(\d+)\]', response)


def compute_citation_accuracy(citations: list[str], source_docs: list[dict]) -> float:
    if not citations:
        return 1.0  # no citations = no false citations
    source_ids = {str(d.get("id", "")) for d in source_docs}
    valid = sum(1 for c in citations if c in source_ids)
    return valid / len(citations)


def validate_citations(citations: list[str], source_docs: list[dict]) -> tuple[bool, list[str]]:
    source_ids = {str(d.get("id", "")) for d in source_docs}
    invalid = [c for c in citations if c not in source_ids]
    return len(invalid) == 0, invalid
