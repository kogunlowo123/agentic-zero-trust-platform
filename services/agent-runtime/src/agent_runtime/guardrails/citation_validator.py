import re


# Matches citation tags like [DOC-1], [DOC-12], [doc-3]
_CITATION_PATTERN = re.compile(r'\[DOC-(\d+)\]', re.IGNORECASE)


def extract_citations(response: str) -> list[str]:
    """Extract [DOC-N] style citation references from a response string.

    Args:
        response: The generated text that may contain citation markers.

    Returns:
        A deduplicated list of citation strings in their original case,
        e.g. ['[DOC-1]', '[DOC-3]'].
    """
    if not response:
        return []

    matches = _CITATION_PATTERN.findall(response)
    # Reconstruct canonical forms and deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for num_str in matches:
        canonical = f"[DOC-{num_str}]"
        if canonical not in seen:
            seen.add(canonical)
            unique.append(canonical)

    return unique


def validate_citations(
    citations: list[str],
    source_docs: list[dict],
) -> tuple[bool, list[str]]:
    """Validate that each citation refers to an actually retrieved source document.

    Source documents are addressed by their 1-based index in the list, so
    [DOC-1] is valid when len(source_docs) >= 1, [DOC-2] when >= 2, etc.

    Args:
        citations: List of citation strings like '[DOC-1]', '[DOC-3]'.
        source_docs: The list of source documents returned by the RAG step.
                     Each dict is expected to have at least a 'content' key.

    Returns:
        A tuple of (all_valid: bool, invalid_citations: list[str]).
        all_valid is True when invalid_citations is empty.
    """
    if not citations:
        return True, []

    invalid: list[str] = []
    for citation in citations:
        match = _CITATION_PATTERN.match(citation)
        if not match:
            invalid.append(citation)
            continue
        doc_index = int(match.group(1))  # 1-based
        if doc_index < 1 or doc_index > len(source_docs):
            invalid.append(citation)

    return len(invalid) == 0, invalid
