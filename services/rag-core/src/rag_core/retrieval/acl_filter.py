"""ACL-based post-retrieval filter."""

from __future__ import annotations

from rag_core.stores.vector_base import SearchResult


def filter_by_acl(
    results: list[SearchResult],
    principal: str,
    acl_groups: list[str],
) -> list[SearchResult]:
    """Remove results the given *principal* is not allowed to see.

    A result is retained when at least one of the following is true:

    * ``allowed_principals`` is absent from the result's metadata (open).
    * ``allowed_principals`` is an empty list (open).
    * ``"*"`` or ``"public"`` is in ``allowed_principals``.
    * *principal* is in ``allowed_principals``.
    * Any element of *acl_groups* is in ``allowed_principals``.

    Args:
        results: Candidate search results to filter.
        principal: The identity of the requesting user (e.g. an email or UPN).
        acl_groups: Group memberships of the requesting user.

    Returns:
        Filtered list retaining only accessible results.
    """
    allowed: list[SearchResult] = []
    for result in results:
        principals: list[str] = result.metadata.get("allowed_principals", [])

        if not principals:
            allowed.append(result)
            continue

        if "*" in principals or "public" in principals:
            allowed.append(result)
            continue

        if principal in principals:
            allowed.append(result)
            continue

        if any(group in principals for group in acl_groups):
            allowed.append(result)
            continue

    return allowed
