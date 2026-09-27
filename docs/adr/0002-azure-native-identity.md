# ADR 0002: Azure Workload Identity and SPIFFE/SPIRE for Workload Identity

**Status:** Accepted  
**Date:** 2024-01-20  
**Deciders:** Architecture Team, Security Team, Cloud Infrastructure Lead  
**Supersedes:** None  
**Related:** ADR 0001 (OPA policy engine depends on SPIFFE SVIDs as principal identifiers)  

---

## Context

Every service and AI agent in the platform needs a cryptographically verifiable identity that can be used to authenticate to other services, authorize access to Azure resources (Key Vault, Storage, OpenAI), and serve as the principal identifier in OPA policy evaluations. The fundamental challenge is eliminating long-lived static credentials (service account keys, shared secrets, connection strings) from all workloads while providing a seamless, developer-friendly identity mechanism that works both within the Kubernetes cluster and for Azure API calls.

We needed an identity solution that satisfies three requirements simultaneously: (1) zero-credential deployments — no secrets in environment variables, CI/CD pipelines, or container images; (2) cryptographic workload attestation — the identity must be provably bound to the specific workload (pod, service account, namespace) rather than being a shared credential; and (3) Azure-native resource access — workloads must be able to authenticate to Azure services (Key Vault, Container Registry, OpenAI) without managing credentials separately.

The two identity layers we considered are: Azure Workload Identity (for Azure resource access) and SPIFFE/SPIRE (for intra-cluster mTLS and policy principal identifiers). These are complementary rather than competing — Azure Workload Identity solves the Azure API authentication problem while SPIFFE/SPIRE solves the east-west authentication problem.

---

## Decision

Use **Azure Workload Identity** for all Azure resource access (Key Vault, ACR, Azure OpenAI, Azure Monitor) and **SPIFFE/SPIRE** for intra-cluster workload identity, mTLS between services, and as the principal identifier in OPA policy evaluations. The two identity systems are integrated: SPIRE attestation uses Kubernetes service account tokens, and Azure Workload Identity uses the same Kubernetes service accounts, creating a unified identity foundation.

---

## Rationale

### Azure Workload Identity eliminates long-lived Azure credentials

Azure Workload Identity uses Kubernetes service account tokens (projected service account tokens) federated with Azure Entra ID through OIDC federation. A workload presents its Kubernetes-issued service account token to Azure Entra ID, which exchanges it for a short-lived Azure access token. This eliminates service principal keys entirely — there are no client secrets or certificates to manage, rotate, or accidentally leak. The Azure SDK supports this transparently via `DefaultAzureCredential`.

### SPIFFE/SPIRE provides cryptographic workload attestation for east-west traffic

SPIFFE (Secure Production Identity Framework For Everyone) and its reference implementation SPIRE provide a standard mechanism for issuing short-lived X.509 SVIDs (SPIFFE Verifiable Identity Documents) to workloads based on cryptographic attestation of the workload's identity. The SPIRE agent on each node attests workloads using the Kubernetes node and workload attestors, verifying pod UID, namespace, and service account before issuing an SVID. This means an agent cannot claim another workload's identity — the identity is bound to the running pod, not to a shared secret.

### SPIFFE URIs as OPA principal identifiers

Using SPIFFE URIs (e.g., `spiffe://zero-trust.example.com/agent/agent-uuid`) as the principal identifier in OPA policy inputs provides several benefits: (1) the identity is cryptographically attested, not self-asserted; (2) the URI structure encodes the trust domain and workload path, enabling hierarchical policy rules; (3) SPIFFE is a CNCF standard, ensuring interoperability with other CNCF-ecosystem tools; and (4) SVIDs are short-lived (1-hour TTL by default), limiting the blast radius of a compromised identity.

### Complementary coverage with no overlap

Azure Workload Identity handles north-south traffic (workload to Azure services), while SPIFFE/SPIRE handles east-west traffic (workload to workload within the cluster). The two systems use the same Kubernetes service accounts as their attestation anchor, creating a coherent identity model. There is no duplication of functionality, and each system is best-in-class for its domain.

---

## Consequences

### Positive

1. **Zero long-lived credentials**: No service principal keys, connection strings, or shared secrets in the deployment. All credentials are ephemeral and automatically rotated.

2. **Cryptographic workload attestation**: Both Azure Workload Identity (via OIDC federation) and SPIFFE/SPIRE (via X.509 SVIDs) provide cryptographic proof of workload identity, not just capability-based access.

3. **Short-lived credential rotation**: Azure access tokens have a 1-hour TTL; SPIFFE SVIDs have a configurable TTL (default 1 hour). Compromise of a credential has a bounded impact window.

4. **Standards-based interoperability**: SPIFFE is a CNCF specification, and Azure Workload Identity implements the OIDC federation standard. Both can interoperate with other platforms and tools that support these standards.

5. **Reduced secret management operational burden**: The External Secrets Operator handles synchronization of non-SPIFFE secrets (e.g., third-party API keys) from Azure Key Vault, and the rotation interval is configurable. No manual secret rotation procedures are required.

### Negative

1. **SPIRE operational complexity**: Running SPIRE in HA mode adds operational overhead. The SPIRE server must be available for SVID issuance, and a SPIRE server outage would prevent new SVID issuance (though existing SVIDs remain valid until their TTL expires).

2. **Dependency on Azure Entra ID availability**: Azure Workload Identity depends on Azure Entra ID for token exchange. Entra ID outages would prevent workloads from obtaining new Azure access tokens, blocking Key Vault and other Azure service access.

3. **Developer experience requires tooling**: Local development with SPIFFE/SPIRE is more complex than using static credentials. Developers need either a local SPIRE installation or mock SVID injection for local testing.

---

## Alternatives Considered

### Kubernetes Secrets with manual rotation

**Pros:** Simple to implement; no additional infrastructure components.  
**Cons:** Long-lived credentials with manual rotation procedures; high risk of credential leakage in CI/CD pipelines and container images; does not scale to many microservices; fails compliance requirements for zero-standing-credentials.  
**Verdict:** Rejected. Fundamentally incompatible with zero trust posture.

### HashiCorp Vault with Vault Agent Injector

**Pros:** Mature secret management; Vault Agent handles dynamic credential injection; broad ecosystem support.  
**Cons:** Additional infrastructure to operate and harden; Vault requires its own highly-available deployment; Azure Key Vault already provides managed HSM-backed secret storage as a first-party Azure service, reducing the need for a separate vault tier.  
**Verdict:** Rejected in favor of Azure Key Vault + External Secrets Operator, which provides equivalent functionality without additional infrastructure complexity in an Azure-native deployment.

---

## Review Notes

This ADR was reviewed by the Architecture Team on 2024-01-20 and approved. The SPIRE deployment design (HA configuration, attestation policy, node pool assignment) is documented in the SPIRE operations runbook. Next review scheduled for 2025-01-20 or upon major version upgrade of either component.
