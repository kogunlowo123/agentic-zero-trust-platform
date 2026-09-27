"""Faithfulness evaluation: fraction of response sentences grounded in source docs."""
from __future__ import annotations
import re


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]


def _is_grounded(sentence: str, source_docs: list[str], min_word_overlap: int = 2) -> bool:
    words = set(sentence.lower().split())
    for doc in source_docs:
        doc_words = set(doc.lower().split())
        if len(words & doc_words) >= min_word_overlap:
            return True
    return False


def compute_faithfulness(response: str, source_docs: list[str]) -> float:
    sentences = _sentences(response)
    if not sentences:
        return 0.0
    grounded = sum(1 for s in sentences if _is_grounded(s, source_docs))
    return grounded / len(sentences)


if __name__ == "__main__":
    response = "T1 agents require a posture score of 70. SVID must start with spiffe://."
    sources = ["posture_threshold[T1] = 70", "startswith(svid, spiffe://zero-trust.example.com/agent/)"]
    score = compute_faithfulness(response, sources)
    print(f"Faithfulness: {score:.3f}")
