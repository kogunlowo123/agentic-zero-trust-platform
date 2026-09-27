# Security Policy

## Supported Versions

Only the most recent release receives security patches. Older versions are unsupported.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

### Preferred Method — GitHub Private Security Advisory

Use GitHub's [private security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) feature:

1. Navigate to the repository on GitHub.
2. Click **Security** → **Advisories** → **Report a vulnerability**.
3. Fill in the form with as much detail as possible.
4. Submit — the report goes directly to maintainers without public disclosure.

### Alternative Method — Email

If you cannot use GitHub advisories, send a PGP-encrypted email to:

**security@example.com**

Include the following information:
- Type of vulnerability (e.g., injection, privilege escalation, insecure defaults)
- Full path(s) of source file(s) related to the vulnerability
- Step-by-step reproduction instructions
- Proof-of-concept or exploit code (if available)
- Impact assessment and potential attack scenarios
- Any suggested remediation

## Responsible Disclosure Timeline

| Milestone | Target |
|-----------|--------|
| Initial acknowledgment | Within 48 hours of report |
| Triage and severity assessment | Within 5 business days |
| Reproduction confirmed / rejected | Within 10 business days |
| Fix developed and reviewed | Within 45 days (critical), 90 days (others) |
| Patch released | Within 7 days of fix completion |
| Public disclosure | Coordinated with reporter, after patch ships |

Reporters may request an embargo extension. Extensions beyond 120 days require exceptional circumstances.

## CVE Handling

When a vulnerability merits a CVE:

1. Maintainers request a CVE ID from [MITRE](https://cveform.mitre.org/) or via GitHub's automated CVE issuance.
2. The CVE ID is shared with the reporter before public disclosure.
3. The GitHub Security Advisory is published simultaneously with the patch, populating the CVE record.
4. Affected users receive notification via GitHub Dependabot alerts.

Severity is scored using [CVSS 3.1](https://www.first.org/cvss/calculator/3.1). CVSS score ranges:

| CVSS Score | Severity | Target Patch Window |
|------------|----------|---------------------|
| 9.0–10.0   | Critical | 45 days |
| 7.0–8.9    | High     | 60 days |
| 4.0–6.9    | Medium   | 90 days |
| 0.1–3.9    | Low      | Next minor release |

## Zero Trust Principles in This Platform

The Agentic Zero Trust Platform is built on the following security foundations:

### 1. Never Trust, Always Verify
Every agent request is authenticated via JWT and re-evaluated through OPA on every call. There are no implicit trust relationships between services.

### 2. Least Privilege Access
Agents are granted only the specific permissions required for a declared task. All access is time-bounded (configurable `duration_minutes`, default 60). Permissions cannot be self-escalated.

### 3. Assume Breach
All inter-service communication is encrypted (TLS 1.3+). The platform logs every access decision with full context. Audit logs are append-only and shipped to OpenSearch within 5 seconds.

### 4. Continuous Verification
`PostureScore` is recalculated after each agent action. A score drop below the configured threshold (default: 60.0) suspends the agent's session and triggers a policy.violation CloudEvent.

### 5. Microsegmentation
Each service operates in an isolated Docker network namespace. OPA policies enforce network-level rules in addition to application-level controls.

### 6. Data-Centric Security
Sensitive data is encrypted at rest (AES-256 via Azure Key Vault CMK) and in transit (TLS). PII fields in the database are encrypted at the column level using pgcrypto.

## Security Features

| Feature | Implementation |
|---------|---------------|
| Authentication | JWT (RS256 in production), Azure AD OIDC |
| Authorization | OPA Rego policies, RBAC with attribute-based extensions |
| Secrets management | Azure Key Vault, no secrets in environment variables in production |
| Container security | Non-root containers, read-only root filesystems, dropped capabilities |
| Dependency scanning | Trivy, Dependabot, pip-audit in CI |
| SAST | Bandit (Python), semgrep rules in CI |
| Secret scanning | TruffleHog in CI/CD pipeline |
| Audit logging | All policy decisions logged with CloudEvents to OpenSearch |
| Rate limiting | Per-agent request throttling at the API gateway |
| Input validation | Pydantic v2 strict mode on all API models |

## Security Contacts

| Role | Contact |
|------|---------|
| Security team | security@example.com |
| Platform owner | @kogunlowo123 |

## Acknowledgments

Reporters who responsibly disclose vulnerabilities will be credited in the GitHub Security Advisory (with their permission) and in the CHANGELOG.
