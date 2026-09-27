## Summary

<!-- Provide a brief description of the changes and motivation. -->

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that causes existing functionality to change)
- [ ] Security fix (addresses a security vulnerability or hardens the platform)
- [ ] Documentation update
- [ ] Infrastructure change (Terraform, Kubernetes, Helm)
- [ ] Policy update (OPA Rego policies)
- [ ] Dependency update

## Changes Made

<!-- List the key changes introduced in this PR. -->

- 
- 
- 

## Testing

<!-- Describe the tests added or modified. Link to test files if applicable. -->

- [ ] Unit tests added / updated (`tests/unit/`)
- [ ] Integration tests added / updated (`tests/integration/`)
- [ ] Security tests added / updated (`tests/security/`)
- [ ] Manual testing steps:

```
1. 
2. 
```

## Security Considerations

<!-- Review the security implications of your changes. -->

- [ ] No credentials, API keys, or secrets added to source code
- [ ] OPA policies validated for new access patterns (`make test-security`)
- [ ] Input validation added for all new API endpoints
- [ ] Dependencies scanned for known vulnerabilities (`uv run safety check`)
- [ ] Bandit SAST check passes (`uv run bandit -r services/ -ll`)

## Zero Trust Impact

<!-- Describe how this change affects the Zero Trust posture of the platform. -->

- [ ] Policy changes have been reviewed and documented
- [ ] New access patterns follow least-privilege principle
- [ ] Agent identity scopes are minimal and justified
- [ ] All privileged actions emit audit events (CloudEvent type `policy.violation` if applicable)
- [ ] No standing permissions introduced (time-bounded access only)

## API / Contract Changes

<!-- If this PR changes any shared contracts, describe the impact. -->

- `PolicyDecision` schema changed: <!-- Yes / No -->
- `AccessRequest` schema changed: <!-- Yes / No -->
- `PostureScore` schema changed: <!-- Yes / No -->
- OPA endpoint behaviour changed: <!-- Yes / No -->

## Checklist

- [ ] `make test` passes locally
- [ ] `make lint` passes locally
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Documentation updated (if applicable)
- [ ] No debug prints or commented-out code left in the diff
- [ ] PR title follows Conventional Commits format (e.g. `feat:`, `fix:`, `chore:`)
