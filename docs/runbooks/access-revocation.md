# Runbook: Emergency Access Revocation

**Version:** 1.0  
**Last Updated:** 2024-06-01  
**Owner:** Security Operations Team  
**Trigger:** Security incident, suspected compromise, or user request  

---

## When to Use

Use this runbook when any of the following conditions are met:

- An agent identity is suspected to be compromised
- Anomalous API access patterns indicate credential theft
- An employee or service account is terminated and requires immediate access removal
- A JIT access grant was issued in error and must be revoked before expiry
- A security incident response requires isolation of a compromised workload
- Key Vault or identity provider logs show unexpected access from an authorized identity

---

## Prerequisites

Before beginning the revocation procedure, ensure you have:

- `kubectl` access to the production AKS cluster (or break-glass credentials — see `deploy/scripts/break_glass.sh`)
- Azure CLI authenticated to the production subscription (`az login --tenant ${AZURE_TENANT_ID}`)
- Access to the platform admin API (`ADMIN_TOKEN` from Key Vault or break-glass procedure)
- Access to Azure Portal or CLI with permissions on the Key Vault and Entra ID tenant
- The `agent_id`, `session_id`, or `principal` identifier of the compromised identity

---

## Procedure

### Step 1: Identify the Compromised Access

Determine the scope of the compromise before revoking to avoid over-broad revocation that could cause unnecessary service disruption.

Retrieve all active sessions for the principal:

```bash
curl -s "https://api.zero-trust.example.com/v1/sessions?principal=${PRINCIPAL_ID}&status=active" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq '.sessions[] | {session_id, agent_id, started_at, last_activity}'
```

List all active JIT grants for the principal:

```bash
curl -s "https://api.zero-trust.example.com/v1/jit/grants?principal=${PRINCIPAL_ID}&status=active" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq '.grants[] | {grant_id, resource, expires_at}'
```

Check Azure Entra ID for active sign-in sessions:

```bash
az ad user show --id "${PRINCIPAL_UPN}" --query "{id:id, displayName:displayName, accountEnabled:accountEnabled}"
```

---

### Step 2: Revoke JIT Access via API

Revoke all active JIT grants for the compromised principal:

```bash
# List and revoke all active JIT grants
GRANTS=$(curl -s "https://api.zero-trust.example.com/v1/jit/grants?principal=${PRINCIPAL_ID}&status=active" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.grants[].grant_id')

for GRANT_ID in ${GRANTS}; do
  echo "Revoking JIT grant: ${GRANT_ID}"
  curl -s -X DELETE "https://api.zero-trust.example.com/v1/jit/grants/${GRANT_ID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -d '{"revoke_reason": "Security incident — emergency revocation"}'
  echo "Revoked: ${GRANT_ID}"
done
```

Suspend the agent identity to prevent new session creation:

```bash
curl -X PATCH "https://api.zero-trust.example.com/v1/agents/${AGENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"status\": \"suspended\", \"suspend_reason\": \"Security incident — revocation in progress\", \"suspended_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
```

---

### Step 3: Invalidate Session Tokens

Terminate all active sessions for the principal:

```bash
# Terminate all active sessions
SESSIONS=$(curl -s "https://api.zero-trust.example.com/v1/sessions?principal=${PRINCIPAL_ID}&status=active" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.sessions[].session_id')

for SESSION_ID in ${SESSIONS}; do
  echo "Terminating session: ${SESSION_ID}"
  curl -s -X DELETE "https://api.zero-trust.example.com/v1/sessions/${SESSION_ID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"
  echo "Terminated: ${SESSION_ID}"
done
```

Revoke the SPIFFE SVID by deleting the Kubernetes ServiceAccount (forces re-attestation on next startup):

```bash
kubectl delete serviceaccount "${SERVICE_ACCOUNT_NAME}" \
  --namespace agentic-zero-trust \
  --ignore-not-found=true
```

Flush the Redis session cache for the principal:

```bash
kubectl exec -n agentic-zero-trust deploy/redis -- \
  redis-cli KEYS "session:${PRINCIPAL_ID}:*" | \
  xargs -I {} kubectl exec -n agentic-zero-trust deploy/redis -- redis-cli DEL {}
```

---

### Step 4: Rotate Credentials

If the compromised identity had access to any secrets or credentials, rotate them immediately.

Rotate the Azure OpenAI API key in Key Vault (if the compromised identity had access):

```bash
az keyvault secret set \
  --vault-name "kv-zero-trust-prod" \
  --name "azure-openai-api-key" \
  --value "$(openssl rand -base64 48)"
```

The External Secrets Operator will synchronize the new value to Kubernetes Secrets within the configured `refreshInterval` (default 1 hour). To force immediate synchronization:

```bash
kubectl annotate externalsecret azure-openai-key \
  --namespace agentic-zero-trust \
  force-sync="$(date +%s)" \
  --overwrite
```

If the JWT signing key may have been exposed, rotate it and invalidate all existing tokens:

```bash
az keyvault secret set \
  --vault-name "kv-zero-trust-prod" \
  --name "jwt-secret-key" \
  --value "$(openssl rand -base64 64)"
```

**WARNING:** Rotating the JWT secret key invalidates ALL active user and service tokens. Coordinate with users before performing this step in non-emergency scenarios.

---

### Step 5: Audit Trail

Create an immutable audit record of all revocation actions taken. Log the following information:

```bash
# Record revocation event in platform audit log
curl -X POST "https://api.zero-trust.example.com/v1/audit/events" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_type\": \"access.revocation\",
    \"operator\": \"$(az account show --query user.name -o tsv)\",
    \"principal_revoked\": \"${PRINCIPAL_ID}\",
    \"sessions_terminated\": $(echo ${SESSIONS} | wc -w | tr -d ' '),
    \"grants_revoked\": $(echo ${GRANTS} | wc -w | tr -d ' '),
    \"credentials_rotated\": true,
    \"revocation_reason\": \"${REVOCATION_REASON}\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"
```

---

## Post-Revocation Verification

After completing the revocation procedure, verify that access has been fully removed:

1. **Confirm no active sessions exist**:
   ```bash
   curl -s "https://api.zero-trust.example.com/v1/sessions?principal=${PRINCIPAL_ID}&status=active" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq '.total_count'
   # Expected: 0
   ```

2. **Confirm agent is suspended**:
   ```bash
   curl -s "https://api.zero-trust.example.com/v1/agents/${AGENT_ID}" \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq '.status'
   # Expected: "suspended"
   ```

3. **Confirm Key Vault secrets updated** (check version timestamp):
   ```bash
   az keyvault secret show --vault-name "kv-zero-trust-prod" \
     --name "azure-openai-api-key" --query attributes.updated
   ```

4. **Confirm OPA policy denies new requests** from the principal by checking the decision log for any new `allow` decisions in the past 5 minutes:
   ```kql
   OPADecisionLogs
   | where TimeGenerated >= ago(5m)
   | where principal == "<PRINCIPAL_ID>"
   | where decision == "allow"
   | count
   ```

---

## Communication Template

Use the following template for notifying affected stakeholders after access revocation:

```
SUBJECT: Emergency Access Revocation — [Agent/Service Name] — [Date]

Access to the Agentic Zero Trust Platform has been revoked for:
  Principal: [agent_id / service name]
  Time of Revocation: [UTC timestamp]
  Reason: [brief description]

Actions Taken:
  - All active sessions terminated ([N] sessions)
  - All JIT grants revoked ([N] grants)
  - Agent identity suspended
  - [Credentials rotated — if applicable]

If you believe this revocation was made in error, contact the Security Operations
team via #security-oncall or security@your-org.com.

Reference: Incident ticket [TICKET-ID]
```

---

## Related Runbooks

- [Policy Violation Response](./policy-violation.md)
- [Break Glass Emergency Access](../../deploy/scripts/break_glass.sh)
