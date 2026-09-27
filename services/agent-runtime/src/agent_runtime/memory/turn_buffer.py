from collections import deque


class TurnBuffer:
    """In-memory sliding-window message buffer for a single agent session.

    Stores messages in OpenAI chat format: {'role': str, 'content': str}.
    When max_turns is exceeded the oldest messages are dropped first.
    """

    def __init__(self, max_turns: int = 20) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self._max_turns = max_turns
        self._buffer: deque[dict] = deque()

    def add(self, role: str, content: str) -> None:
        """Append a message and evict the oldest if the buffer is full.

        Args:
            role: OpenAI message role — 'system', 'user', or 'assistant'.
            content: The message text.
        """
        self._buffer.append({"role": role, "content": content})
        while len(self._buffer) > self._max_turns:
            self._buffer.popleft()

    def get_messages(self) -> list[dict]:
        """Return all buffered messages in chronological order."""
        return list(self._buffer)

    def clear(self) -> None:
        """Remove all messages from the buffer."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
