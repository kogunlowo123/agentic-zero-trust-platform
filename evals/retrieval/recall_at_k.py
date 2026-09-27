"""Retrieval evaluation metrics: Recall@K."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable, NamedTuple


class RecallResult(NamedTuple):
    query_id: str
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    question: str


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / len(relevant)


def evaluate_dataset(
    golden_path: Path,
    retriever_fn: Callable[[str], list[str]],
) -> list[RecallResult]:
    results = []
    with open(golden_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            retrieved = retriever_fn(item["question"])
            relevant = item.get("relevant_doc_ids", [item.get("source_doc", "")])
            if isinstance(relevant, str):
                relevant = [relevant]
            results.append(RecallResult(
                query_id=item["id"],
                recall_at_1=recall_at_k(retrieved, relevant, 1),
                recall_at_3=recall_at_k(retrieved, relevant, 3),
                recall_at_5=recall_at_k(retrieved, relevant, 5),
                recall_at_10=recall_at_k(retrieved, relevant, 10),
                question=item["question"],
            ))
    return results


if __name__ == "__main__":
    import sys
    golden = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/datasets/golden/zero-trust-qa-pairs.jsonl")

    def dummy_retriever(q: str) -> list[str]:
        return []

    results = evaluate_dataset(golden, dummy_retriever)
    for r in results:
        print(f"{r.query_id}: R@5={r.recall_at_5:.3f}")
