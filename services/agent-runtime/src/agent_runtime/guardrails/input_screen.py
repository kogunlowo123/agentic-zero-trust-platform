import re

# Patterns that indicate prompt injection or policy bypass attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"disregard\s+(?:your\s+)?(?:previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+(?:now\s+)?(?:a\s+)?(?:different|new|unrestricted)\s+(?:ai|agent|assistant)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:policy|security|controls?|guardrails?)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:if\s+you\s+(?:have\s+)?no\s+restrictions?)", re.IGNORECASE),
    re.compile(r"pretend\s+(?:there\s+are\s+no\s+rules?|you\s+are\s+unrestricted)", re.IGNORECASE),
    re.compile(r"override\s+(?:your\s+)?(?:safety|security|policy)\s+(?:settings?|controls?)", re.IGNORECASE),
    re.compile(r"reveal\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?)", re.IGNORECASE),
]

# Patterns that indicate credential/token exfiltration attempts
_EXFIL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"print\s+(?:your\s+)?(?:api\s+key|access\s+token|secret|password|credential)", re.IGNORECASE),
    re.compile(r"(?:send|transmit|forward|exfiltrate)\s+(?:the\s+)?(?:token|key|secret|credential)", re.IGNORECASE),
    re.compile(r"(?:what\s+is|tell\s+me)\s+(?:the\s+)?(?:api\s+key|bearer\s+token|service\s+account)", re.IGNORECASE),
    re.compile(r"AZURE_CLIENT_SECRET|AZURE_CLIENT_ID|AZURE_TENANT_ID", re.IGNORECASE),
    re.compile(r"(?:dump|list|show)\s+(?:all\s+)?(?:environment\s+variables?|env\s+vars?|secrets?)", re.IGNORECASE),
    re.compile(r"curl\s+.*https?://", re.IGNORECASE),
    re.compile(r"wget\s+.*https?://", re.IGNORECASE),
    re.compile(r"(?:post|send)\s+data\s+to\s+(?:external|remote|third.party)", re.IGNORECASE),
]


async def screen_input(text: str) -> tuple[bool, str]:
    """Screen input text for prompt injection and credential exfiltration attempts.

    Args:
        text: The input text to screen.

    Returns:
        A tuple of (safe: bool, reason: str).
        If safe is True, the input is considered safe and reason is empty.
        If safe is False, reason explains why the input was flagged.
    """
    if not text or not text.strip():
        return True, ""

    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, (
                f"Input contains potential prompt injection: matched pattern '{pattern.pattern}' "
                f"at position {match.start()}"
            )

    for pattern in _EXFIL_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, (
                f"Input contains potential credential exfiltration attempt: "
                f"matched pattern '{pattern.pattern}' at position {match.start()}"
            )

    return True, ""
