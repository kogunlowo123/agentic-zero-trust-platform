from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Document:
    """Represents a loaded document before chunking."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLoader:
    """Minimum interface every loader must satisfy."""

    def load(self, path: Path) -> list[Document]:  # noqa: ARG002
        raise NotImplementedError


class LoaderRegistry:
    """Registry that maps file extensions to loader classes.

    Usage::

        @registry.register(".pdf")
        class MyLoader(BaseLoader):
            ...

        loader = registry.get(Path("policy.pdf"))
        docs = loader.load(Path("policy.pdf"))
    """

    def __init__(self) -> None:
        self._map: dict[str, type[BaseLoader]] = {}

    def register(self, extension: str):
        """Class decorator that registers a loader for the given extension.

        Args:
            extension: File extension including the leading dot, e.g. ``".pdf"``.

        Returns:
            The decorator function.
        """
        ext = extension.lower()

        def decorator(cls: type[BaseLoader]) -> type[BaseLoader]:
            self._map[ext] = cls
            return cls

        return decorator

    def get(self, path: Path) -> BaseLoader:
        """Return an instantiated loader suitable for *path*.

        Args:
            path: Path to the file that needs loading.

        Returns:
            An instantiated loader.

        Raises:
            KeyError: If no loader is registered for the file's extension.
        """
        ext = path.suffix.lower()
        try:
            loader_cls = self._map[ext]
        except KeyError:
            supported = ", ".join(sorted(self._map.keys()))
            raise KeyError(
                f"No loader registered for extension '{ext}'. "
                f"Supported extensions: {supported}"
            ) from None
        return loader_cls()

    @property
    def extensions(self) -> list[str]:
        """Return the list of registered extensions."""
        return list(self._map.keys())


# Module-level singleton used throughout the package.
registry = LoaderRegistry()

# Auto-register built-in loaders by importing the modules that use
# @registry.register.  The imports happen here rather than at module top-level
# to avoid circular-import issues while still guaranteeing the loaders are
# registered whenever someone does ``from rag_core.ingestion.loader_registry
# import registry``.

def _auto_discover() -> None:  # pragma: no cover
    try:
        from rag_core.ingestion import pdf_loader as _  # noqa: F401
        from rag_core.ingestion import html_loader as __  # noqa: F401
    except ImportError:
        pass


_auto_discover()
