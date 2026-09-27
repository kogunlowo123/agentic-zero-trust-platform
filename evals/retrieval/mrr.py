"""Mean Reciprocal Rank (MRR) evaluation."""
from __future__ import annotations


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(queries: list[dict]) -> float:
    if not queries:
        return 0.0
    rrs = []
    for q in queries:
        retrieved = q.get("retrieved_ids", [])
        relevant = set(q.get("relevant_ids", []))
        rrs.append(reciprocal_rank(retrieved, relevant))
    return sum(rrs) / len(rrs)


if __name__ == "__main__":
    import json, sys
    data = json.loads(sys.stdin.read())
    mrr = mean_reciprocal_rank(data)
    print(f"MRR: {mrr:.4f}")
