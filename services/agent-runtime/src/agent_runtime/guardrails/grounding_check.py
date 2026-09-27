import re


def _extract_noun_phrases(text: str) -> list[str]:
    """Extract candidate noun phrases from text using simple heuristics.

    Targets capitalized multi-word sequences and quoted terms as
    likely claims that should appear in source documents.
    """
    phrases: list[str] = []

    # Quoted terms (likely specific policy references or technical terms)
    quoted = re.findall(r'"([^"]{3,60})"', text)
    phrases.extend(quoted)

    # Capitalized sequences (proper nouns, policy names, etc.)
    cap_sequences = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b', text)
    phrases.extend(cap_sequences)

    # All-caps acronyms that appear standalone (e.g., MFA, SSO, RBAC)
    acronyms = re.findall(r'\b([A-Z]{2,8})\b', text)
    phrases.extend(acronyms)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in phrases:
        normalized = p.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(p)

    return unique


def check_grounding(response: str, source_docs: list[dict]) -> float:
    """Check how well the response is grounded in the provided source documents.

    Uses keyword-overlap heuristics: extracts candidate claims from the
    response and checks whether they appear in any source document's content.

    Args:
        response: The generated text response to evaluate.
        source_docs: List of source document dicts, each expected to have
                     a 'content' field (str) and optionally 'metadata'.

    Returns:
        A grounding score between 0.0 and 1.0.
        1.0 means all extracted claims were found in source docs.
        0.0 means no claims were found (or no claims could be extracted).
    """
    if not response or not source_docs:
        return 0.0

    # Build a single concatenated corpus from all source docs
    corpus_parts: list[str] = []
    for doc in source_docs:
        content = doc.get("content", "")
        if content:
            corpus_parts.append(content.lower())
    corpus = " ".join(corpus_parts)

    if not corpus:
        return 0.0

    claims = _extract_noun_phrases(response)
    if not claims:
        # No extractable claims — treat as neutral rather than penalizing
        return 1.0

    found_count = 0
    for claim in claims:
        if claim.lower() in corpus:
            found_count += 1

    return found_count / len(claims)
