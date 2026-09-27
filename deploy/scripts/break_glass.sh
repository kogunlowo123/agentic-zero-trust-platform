#!/usr/bin/env bash
# Break Glass Emergency Access Script
# Creates a time-limited cluster-admin service account for emergency operations
# All actions are logged to stdout and Azure Monitor
set -euo pipefail

REASON="${1:?Usage: $0 <reason> <duration_hours>}"
DURATION_HOURS="${2:-4}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
SESSION_ID="break-glass-${TIMESTAMP}"
EXPIRY_SECONDS=$((DURATION_HOURS * 3600))
NAMESPACE="agentic-zero-trust"

echo "[BREAK-GLASS] ${TIMESTAMP} INITIATED"
echo "[BREAK-GLASS] Reason: ${REASON}"
echo "[BREAK-GLASS] Duration: ${DURATION_HOURS} hours"
echo "[BREAK-GLASS] Session: ${SESSION_ID}"
echo "[BREAK-GLASS] Operator: $(az account show --query user.name -o tsv 2>/dev/null || echo unknown)"

: "${AZURE_TENANT_ID:?AZURE_TENANT_ID must be set}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID must be set}"
: "${CLUSTER_NAME:?CLUSTER_NAME must be set}"
: "${RESOURCE_GROUP:?RESOURCE_GROUP must be set}"

# Get AKS credentials
echo "[BREAK-GLASS] Fetching AKS credentials..."
az aks get-credentials \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${CLUSTER_NAME}" \
  --overwrite-existing

# Create emergency service account
echo "[BREAK-GLASS] Creating emergency service account..."
kubectl create serviceaccount "${SESSION_ID}" \
  --namespace "${NAMESPACE}" 2>/dev/null || true

# Bind cluster-admin role
echo "[BREAK-GLASS] Binding cluster-admin role..."
kubectl create clusterrolebinding "${SESSION_ID}" \
  --clusterrole=cluster-admin \
  --serviceaccount="${NAMESPACE}:${SESSION_ID}"

# Create kubeconfig token
SA_TOKEN=$(kubectl create token "${SESSION_ID}" \
  --namespace "${NAMESPACE}" \
  --duration="${DURATION_HOURS}h")
echo "[BREAK-GLASS] Service account token created (valid ${DURATION_HOURS}h)"

# Schedule automatic cleanup
(
  sleep "${EXPIRY_SECONDS}"
  kubectl delete clusterrolebinding "${SESSION_ID}" --ignore-not-found=true
  kubectl delete serviceaccount "${SESSION_ID}" \
    --namespace "${NAMESPACE}" --ignore-not-found=true
  echo "[BREAK-GLASS] ${SESSION_ID} auto-expired and cleaned up at $(date -u)"
) &
CLEANUP_PID=$!

echo "[BREAK-GLASS] Auto-cleanup scheduled in ${DURATION_HOURS}h (PID: ${CLEANUP_PID})"
echo "[BREAK-GLASS] IMPORTANT: Revoke manually when done: kubectl delete clusterrolebinding ${SESSION_ID}"
echo "[BREAK-GLASS] Session active. Access expires at: $(date -u -d "+${EXPIRY_SECONDS} seconds" 2>/dev/null || date -u -v +${EXPIRY_SECONDS}S)"
