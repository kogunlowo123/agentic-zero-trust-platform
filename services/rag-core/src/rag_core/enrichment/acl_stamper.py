"""ACL stamper: attaches allowed-principals and classification to chunks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rag_core.chunking.base import Chunk


def _load_sidecar_acl(source_file: str) -> list[str] | None:
    """Try to read an ACL sidecar YAML file beside *source_file*.

    The sidecar file is expected to be named ``<source_file>.acl.yaml``.

    Returns the ``allowed_principals`` list from the file, or ``None`` if the
    file does not exist or cannot be parsed.
    """
    if not source_file:
        return None
    sidecar = Path(source_file + ".acl.yaml")
    if not sidecar.is_file():
        sidecar = Path(source_file).with_suffix(".acl.yaml")
    if not sidecar.is_file():
        return None
    try:
        data: Any = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            principals = data.get("allowed_principals", [])
            if isinstance(principals, list):
                return [str(p) for p in principals]
    except Exception:
        pass
    return None


def _derive_classification(acl: list[str]) -> str:
    """Derive a classification label from the ACL list.

    - Empty ACL or contains ``"*"`` / ``"public"`` → ``PUBLIC``
    - ACL with generic group names → ``INTERNAL``
    - Explicit principal list → ``CONFIDENTIAL``
    """
    if not acl or "*" in acl or "public" in acl:
        return "PUBLIC"
    # Simple heuristic: if all entries look like group names (no @), INTERNAL
    if all("@" not in entry and not entry.startswith("user:") for entry in acl):
        return "INTERNAL"
    return "CONFIDENTIAL"


class ACLStamper:
    """Stamps each chunk with ACL metadata.

    For each chunk the stamper will:
    1. Check for a YAML sidecar file beside the source document.
    2. Fall back to the *acl* argument if no sidecar exists.
    3. Record ``allowed_principals`` and ``classification`` in the metadata.

    Args:
        default_classification: Used when the ACL list would normally map to
            ``PUBLIC`` but you want a stricter default.
    """

    def __init__(self, default_classification: str = "INTERNAL") -> None:
        self.default_classification = default_classification

    def stamp(self, chunks: list[Chunk], acl: list[str]) -> list[Chunk]:
        """Apply ACL metadata to every chunk.

        Args:
            chunks: Chunks to stamp.
            acl: Fallback list of allowed principals (used when no sidecar
                is found).

        Returns:
            The same list with ACL metadata applied in-place.
        """
        for chunk in chunks:
            source_file = chunk.metadata.get("source_file", "")
            sidecar_acl = _load_sidecar_acl(source_file)
            effective_acl = sidecar_acl if sidecar_acl is not None else acl

            classification = _derive_classification(effective_acl)

            chunk.metadata["allowed_principals"] = effective_acl
            chunk.metadata["classification"] = classification

        return chunks
