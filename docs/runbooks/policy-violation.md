# Runbook: Policy Violation Response

**Version:** 1.0  
**Last Updated:** 2024-06-01  
**Owner:** Security Operations Team  
**On-Call Rotation:** #security-oncall (PagerDuty)  

---

## Overview

This runbook describes the response procedure for alerts triggered by policy violation events in the Agentic Zero Trust Platform. Policy violations occur when an agent or service receives a `deny` decision from the OPA policy engine, which may indicate a misconfigured agent, a compromised principal, a policy bug, or an active bypass attempt. The severity of the response scales with the frequency and nature of the violation.

All policy evaluation decisions are logged to Azure Monitor Log Analytics with a 90-day retention period. The OPA decision log includes the full input context (principal, resource, action, reasons) and a globally unique `decision_id` for correlation with application traces.

---

## Alert Conditions

This runbook is triggered by any of the following alert conditions:

| Alert Name | Source | Trigger Condition |
|---|---|---|
| `PolicyBypassAttempt` | Sigma / Azure Sentinel | Same principal receives > 5 denies in 5 minutes |
| `AgentToolScopeViolation` | Agent Runtime logs | Any `tool.call.attempt` with `violation=true` |
| `HighDenyRate` | Prometheus / Grafana | Deny rate > 10% of total evaluations over 5 minutes |
| `UnknownPrincipalDeny` | OPA decision log | Deny with reason `PRINCIPAL_NOT_FOUND` |
| `ElevatedPrivilegeDeny` | OPA decision log | Deny with reason `ELEVATION_OF_PRIVILEGE_ATTEMPT` |

---

## Severity Classification

| Severity | Criteria | Response SLO | Notification |
|---|---|---|---|
| **P1 — Critical** | Active privilege escalation attempt; unknown principal accessing sensitive resources; > 20 denies in 5 min from same principal | Acknowledge in 5 min, resolve in 1 hour | Page on-call security + incident commander |
| **P2 — High** | Repeated tool scope violations from same agent; deny rate > 20% over 10 min; agent accessing out-of-scope resources | Acknowledge in 15 min, resolve in 4 hours | Page on-call security |
| **P3 — Medium** | Single tool scope violation (likely misconfiguration); deny rate 10–20% over 10 min | Acknowledge in 1 hour, resolve in 1 business day | Alert in #security-alerts Slack channel |
| **P4 — Low** | Isolated denies from new agents in warm-up period; known transient misconfiguration | Acknowledge in 4 hours, resolve in 2 business days | Ticket in tracking system |

---

## Step 1: Initial Triage

### 1.1 Acknowledge the alert

Acknowledge the alert in PagerDuty or Sentinel to prevent duplicate pages and record the start of your investigation.

### 1.2 Identify the affected principal

Run the following KQL query in Azure Monitor Log Analytics to identify the principal and deny pattern:

```kql
OPADecisionLogs
| where TimeGenerated >= ago(30m)
| where decision == "deny"
| summarize
    DenyCount = count(),
    Resources = make_set(resource, 10),
    Actions = make_set(action, 10),
    ReasonCodes = make_set(tostring(reasons), 10),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated)
    by principal
| order by DenyCount desc
| take 20
```

### 1.3 Check if the principal is a known agent

Verify whether the principal is registered in the agent registry:

```bash
curl -s "https://api.zero-trust.example.com/v1/agents/{agent_id}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq .
```

If the principal is not found (`404`), escalate to P1 immediately and proceed to Step 3.

### 1.4 Review the deny reasons

Common deny reason codes and their meanings:

| Reason Code | Meaning | Likely Cause |
|---|---|---|
| `POSTURE_SCORE_BELOW_THRESHOLD` | Agent posture score insufficient | MDM enrollment lapsed; posture signals stale |
| `TOOL_NOT_IN_SCOPE` | Tool not in agent's allowed_tools | Policy update not yet propagated; agent misconfigured |
| `JIT_GRANT_EXPIRED` | JIT access grant has expired | Agent ran longer than grant duration |
| `PRINCIPAL_NOT_FOUND` | Principal not in identity store | Compromised/unknown identity; SPIRE attestation failure |
| `DELEGATION_DEPTH_EXCEEDED` | Delegation chain too deep | Agent spawning sub-agents beyond allowed depth |
| `ELEVATION_OF_PRIVILEGE_ATTEMPT` | Requested permissions exceed grants | Potential jailbreak or policy bypass attempt |
| `RESOURCE_CLASSIFICATION_MISMATCH` | Agent tier insufficient for resource | T1 agent attempting T0 resource access |

---

## Step 2: Investigation

### 2.1 Retrieve the full OPA decision context

Use the `decision_id` from the alert to retrieve the full decision context:

```kql
OPADecisionLogs
| where decision_id == "<decision_id_from_alert>"
| project TimeGenerated, principal, resource, action, decision, reasons, input_snapshot
```

### 2.2 Check agent session logs for surrounding context

```kql
AgentRuntimeLogs
| where TimeGenerated between (ago(30m) .. now())
| where session_id == "<session_id>"
| order by TimeGenerated asc
| project TimeGenerated, event_type, tool_name, agent_id, session_id, message
```

### 2.3 Check for correlated anomalies

Look for correlated events that may indicate a broader attack pattern:

```bash
# Check for sign-in anomalies for the same principal
# Run the entra-agent-anomaly.kql query with the principal filtered
```

```kql
SigninLogs
| where TimeGenerated >= ago(1h)
| where UserPrincipalName contains "<principal_identifier>"
| project TimeGenerated, UserPrincipalName, ResultType, IPAddress, AppDisplayName, ConditionalAccessStatus
| order by TimeGenerated desc
```

### 2.4 Check Key Vault access logs

If the deny involves credential access, check Key Vault audit logs:

```kql
AzureDiagnostics
| where TimeGenerated >= ago(1h)
| where ResourceType == "VAULTS"
| where CallerObjectId == "<principal_object_id>"
| project TimeGenerated, OperationName, ResultType, id_s, CallerIPAddress
| order by TimeGenerated desc
```

---

## Step 3: Remediation

### 3.1 Remediation for misconfiguration (P3/P4)

If the denial is due to a policy misconfiguration or stale posture signals:

1. **Update the agent profile** if `allowed_tools` is missing a required tool:
   ```bash
   curl -X PATCH "https://api.zero-trust.example.com/v1/agents/{agent_id}" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"allowed_tools": ["tool_a", "tool_b", "tool_c"]}'
   ```

2. **Refresh posture signals** if posture score is stale:
   ```bash
   curl -X POST "https://api.zero-trust.example.com/v1/agents/{agent_id}/posture/refresh" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}"
   ```

3. **Extend JIT grant** if an active grant has expired for a legitimate operation:
   ```bash
   curl -X POST "https://api.zero-trust.example.com/v1/jit/grants/{grant_id}/extend" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" \
     -d '{"additional_seconds": 3600}'
   ```

### 3.2 Remediation for active bypass attempt (P1/P2)

If the investigation indicates an active attack or compromise:

1. **Revoke the agent session immediately**:
   ```bash
   curl -X DELETE "https://api.zero-trust.example.com/v1/sessions/{session_id}" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}"
   ```

2. **Disable the agent identity**:
   ```bash
   curl -X PATCH "https://api.zero-trust.example.com/v1/agents/{agent_id}" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" \
     -d '{"status": "suspended", "suspend_reason": "Security investigation"}'
   ```

3. **Initiate the access revocation runbook** (see `docs/runbooks/access-revocation.md`) for full credential rotation.

---

## Step 4: Communication

### 4.1 Internal communication

For P1/P2 incidents, post a status update in the `#security-incidents` Slack channel within 15 minutes of acknowledgement using the template:

```
SECURITY INCIDENT UPDATE — [TIMESTAMP]
Severity: P1/P2
Summary: [2-sentence description of the violation]
Principal Affected: [agent_id or service name]
Status: [Investigating / Contained / Resolved]
Next Update: [time]
```

### 4.2 Stakeholder notification

For P1 incidents, notify the following stakeholders within 30 minutes:
- CISO (direct Slack message)
- Platform Engineering Lead (#platform-engineering channel)
- Product Security (#product-security channel)

---

## Step 5: Post-Incident Review

All P1 and P2 policy violation incidents require a post-incident review (PIR) within 5 business days. The PIR must cover:

1. **Timeline**: Chronological sequence of events from first violation to resolution
2. **Root cause**: Technical and process root causes identified
3. **Impact**: Systems, data, and users affected
4. **Detection gap**: Whether existing detections fired appropriately and promptly
5. **Action items**: Specific, time-bound improvements to prevent recurrence

The PIR document is stored in the `docs/post-incident-reviews/` directory and linked from the incident ticket.

---

## Escalation Matrix

| Condition | Escalate To | Method | SLO |
|---|---|---|---|
| Unknown principal accessing any resource | On-call Security + CISO | PagerDuty + direct message | Immediate |
| P1 not resolved within 1 hour | Incident Commander | PagerDuty escalation | 1 hour |
| Suspected data exfiltration | CISO + Legal + Compliance | Phone + email | Immediate |
| Policy engine unavailable | Platform Engineering On-Call | PagerDuty | 5 minutes |
| Multiple agents simultaneously compromised | CISO + CTO | Direct phone | Immediate |

---

## Related Resources

- [Access Revocation Runbook](./access-revocation.md)
- [OPA Policy Bundle Repository](https://github.com/kogunlowo123/agentic-zero-trust-platform/tree/main/policy)
- [Sigma Detection Rules](../../security/detections/sigma/)
- [KQL Detection Queries](../../security/detections/kql/)
- [STRIDE Threat Model](../../security/threat-models/stride/zero-trust-plane.md)
- [Azure Monitor Log Analytics Workspace](https://portal.azure.com) (link configured in deployment)
- [PagerDuty Service](https://your-org.pagerduty.com) (link configured per environment)
