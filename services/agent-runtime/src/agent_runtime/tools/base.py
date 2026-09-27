from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Abstract base class for all zero-trust agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""

    @property
    @abstractmethod
    def schema(self) -> dict:
        """JSON Schema describing the tool's input parameters."""

    @abstractmethod
    async def call(self, **kwargs) -> dict:
        """Execute the tool with the given keyword arguments.

        Returns a dict containing the tool result.
        Raises RuntimeError on unrecoverable failures.
        """
