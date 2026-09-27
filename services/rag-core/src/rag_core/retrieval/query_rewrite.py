"""Query rewriter for zero-trust domain queries."""

from __future__ import annotations

import re

# Abbreviation expansion map.
_EXPANSIONS: dict[str, str] = {
    r"\bZTA\b": "Zero Trust Architecture",
    r"\bZTNA\b": "Zero Trust Network Access",
    r"\bJIT\b": "Just-in-Time",
    r"\bJEA\b": "Just Enough Access",
    r"\bJAT\b": "Just-Enough-Administration Token",
    r"\bIAM\b": "Identity and Access Management",
    r"\bIDaaS\b": "Identity as a Service",
    r"\bMFA\b": "Multi-Factor Authentication",
    r"\bPAM\b": "Privileged Access Management",
    r"\bSDP\b": "Software-Defined Perimeter",
    r"\bSASE\b": "Secure Access Service Edge",
    r"\bSWG\b": "Secure Web Gateway",
    r"\bCASB\b": "Cloud Access Security Broker",
    r"\bEDR\b": "Endpoint Detection and Response",
    r"\bXDR\b": "Extended Detection and Response",
    r"\bSOAR\b": "Security Orchestration Automation and Response",
    r"\bSIEM\b": "Security Information and Event Management",
    r"\bOPA\b": "Open Policy Agent",
    r"\bRBAC\b": "Role-Based Access Control",
    r"\bABAC\b": "Attribute-Based Access Control",
    r"\bPBAC\b": "Policy-Based Access Control",
    r"\bNIST\b": "National Institute of Standards and Technology",
    r"\bSP 800-207\b": "NIST Special Publication 800-207 Zero Trust Architecture",
    r"\bSVID\b": "SPIFFE Verifiable Identity Document",
    r"\bSPIFFE\b": "Secure Production Identity Framework for Everyone",
    r"\bmTLS\b": "Mutual TLS",
    r"\bPKI\b": "Public Key Infrastructure",
    r"\bCA\b": "Certificate Authority",
}

# Patterns that indicate a policy-type query and should receive a domain prefix.
_POLICY_SIGNALS = re.compile(
    r"\b(policy|policies|compliance|requirement|control|standard|"
    r"nist|framework|guideline|mandate|rule|regulation)\b",
    re.IGNORECASE,
)

_DOMAIN_PREFIX = "zero trust policy: "


class QueryRewriter:
    """Rewrites user queries to improve recall on the zero-trust corpus.

    Two transformations are applied:
    1. Abbreviation expansion: known acronyms are replaced by their full forms.
    2. Domain prefix injection: queries that appear to be about policy or
       compliance receive the prefix ``"zero trust policy: "`` so the dense
       retriever places them closer to policy document embeddings.
    """

    async def rewrite(self, query: str) -> str:
        """Rewrite *query* for improved retrieval.

        Args:
            query: Raw user query string.

        Returns:
            Rewritten query string.
        """
        rewritten = query

        # Expand abbreviations.
        for pattern, expansion in _EXPANSIONS.items():
            rewritten = re.sub(pattern, expansion, rewritten)

        # Inject domain context prefix for policy queries.
        if _POLICY_SIGNALS.search(rewritten) and not rewritten.lower().startswith(
            "zero trust"
        ):
            rewritten = _DOMAIN_PREFIX + rewritten

        return rewritten
