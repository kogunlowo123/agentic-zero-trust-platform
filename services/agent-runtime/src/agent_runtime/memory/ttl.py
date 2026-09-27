POLICY_TTLS: dict[str, int] = {
    "session": 3600,
    "episodic": 86400,
    "posture": 300,
    "decision": 7200,
}


class TTLPolicy:
    """Centralised TTL policy manager.

    Looks up the TTL for a named memory type.  Unknown types fall back
    to *default_ttl*.

    Args:
        default_ttl: Seconds to use when the requested type is not found.
                     Defaults to 3600 (one hour).
    """

    def __init__(self, default_ttl: int = 3600) -> None:
        self.default_ttl = default_ttl

    def get_ttl(self, memory_type: str) -> int:
        """Return the TTL in seconds for the given memory type.

        Args:
            memory_type: One of the keys defined in POLICY_TTLS, or any
                         custom type name.

        Returns:
            Integer TTL in seconds.
        """
        return POLICY_TTLS.get(memory_type, self.default_ttl)
