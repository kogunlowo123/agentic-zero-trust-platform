# STRIDE Threat Model: Zero Trust Control Plane

**Version:** 1.0  
**Date:** 2024-06-01  
**Status:** Approved  
**Review Cycle:** Quarterly  
**Owner:** Security Architecture Team  

---

## 1. System Description

The Agentic Zero Trust Control Plane is the core enforcement fabric of the platform. It acts as the single source of truth for all authorization decisions affecting AI agents operating within the enterprise environment. Every agent action — tool invocations, data retrievals, external API calls, and credential access — is mediated through this plane before execution. The control plane combines continuous identity verification (via SPIFFE/SVID), real-time posture assessment, and contextual policy evaluation to implement a "never trust, always verify" model across all agent workloads.

The control plane comprises six primary subsystems: the API Gateway (edge ingress and TLS termination), the OPA Policy Engine (Rego-based evaluation with audit logging), the Identity Broker (SPIFFE/SVID issuance and OIDC token exchange), the RAG Pipeline (hybrid dense/sparse retrieval serving agent context), the Agent Runtime (isolated execution sandbox per agent session), and the Secrets Vault (Azure Key Vault with workload identity-based access). These components communicate over mutual TLS within the cluster and are isolated by Kubernetes namespace with NetworkPolicy enforcement.

The threat model covers all data flows between subsystems and all external integrations, including Azure Entra ID (identity provider), Azure Container Registry (image supply chain), Azure Monitor (telemetry sink), and external LLM endpoints (Azure OpenAI). The trust boundary is drawn at the AKS cluster ingress; all traffic from outside the cluster boundary is treated as untrusted until authenticated and authorized. Internal east-west traffic between services is authenticated via SPIFFE SVIDs and authorized via OPA policies evaluated at the Envoy sidecar layer.

---

## 2. System Components

| Component | Purpose | Trust Zone | Notes |
|---|---|---|---|
| API Gateway (Envoy/NGINX) | TLS termination, rate limiting, JWT validation, request routing | DMZ / Untrusted Ingress | First hop for all external requests |
| OPA Policy Engine | Rego policy evaluation, decision logging, bundle management | Trusted Internal | CNCF graduated, air-gapped bundle updates |
| Identity Broker (SPIRE) | SVID issuance, OIDC token exchange, workload attestation | Highly Trusted | Root of trust for all workload identities |
| RAG Pipeline | Hybrid document retrieval, context injection, embedding management | Trusted Internal | Access to document corpus, embedding store |
| Agent Runtime | Isolated agent execution, tool call enforcement, session management | Partially Trusted | Executes external code; strongest sandboxing |
| Azure Key Vault | Secret storage, key management, certificate issuance | External Trusted | Accessed via workload identity only |
| Azure Entra ID | Identity provider, OIDC issuer, group membership | External Trusted | Federated identity source |
| Azure OpenAI | LLM inference endpoint | External Semi-Trusted | Receives redacted prompts and contexts |
| PostgreSQL (pgvector) | Vector store, agent state, audit log persistence | Trusted Internal | Contains sensitive agent session data |
| Azure Monitor / OTEL | Telemetry ingestion, alerting, log storage | External Trusted | Receives PII-scrubbed telemetry |

---

## 3. Data Flow Description

1. **Client → API Gateway**: External client (human or machine) sends HTTPS request with Bearer JWT issued by Azure Entra ID. Gateway validates TLS, checks JWT signature and claims, enforces rate limits, and forwards to the API service with an X-Request-ID header injected.

2. **API Gateway → OPA Engine**: For every authorized API call that modifies agent state or triggers privileged actions, the API service calls OPA's `/v1/data/zero_trust/allow` endpoint with a structured input document containing principal claims, resource descriptor, action, and current posture score.

3. **OPA Engine → Decision Log**: Every evaluation decision (allow or deny) is written to the OPA decision log stream, which is consumed by the OTEL collector and forwarded to Azure Monitor with the full input context and reason list.

4. **API Service → Identity Broker (SPIRE)**: Before issuing agent credentials, the API service calls SPIRE's workload API to obtain a fresh SVID for the agent session. The SVID is scoped to the agent's SPIFFE URI (`spiffe://zero-trust.example.com/agent/{agent_id}`).

5. **Agent Runtime → Tool Call Interceptor**: When an agent invokes a tool, the Agent Runtime intercepts the call, validates the tool name against the agent's `allowed_tools` list (enforced via OPA), signs the outbound request with the agent's SVID, and logs the event.

6. **Agent Runtime → RAG Pipeline**: Agent context retrieval requests flow from the Agent Runtime to the RAG Pipeline over mTLS. The RAG Pipeline applies document-level ACL policies before returning chunks to ensure agents only receive documents their policy permits.

7. **RAG Pipeline → PostgreSQL (pgvector)**: Embedding similarity searches use pgvector. Queries are parameterized; results are filtered by document ACL before returning to the caller.

8. **Secrets Access → Azure Key Vault**: Service workloads use the External Secrets Operator with workload identity to pull secrets into Kubernetes Secrets. Direct Key Vault access from application code is disallowed by policy.

9. **Agent Runtime → Azure OpenAI**: Outbound LLM requests are proxied through the OTEL-instrumented API service, which scrubs PII from prompts before forwarding. Response content is logged (truncated) for audit purposes.

10. **Telemetry → Azure Monitor**: All services emit OTEL traces, metrics, and logs to the OTEL Collector, which applies PII scrubbing transforms before exporting to Azure Monitor / Application Insights.

---

## 4. Data Flow Diagram

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                   EXTERNAL TRUST BOUNDARY                │
                        └─────────────────────────────────────────────────────────┘
                                              │ HTTPS / JWT
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│  AKS CLUSTER — agentic-zero-trust namespace                                        │
│                                                                                    │
│   ┌──────────────┐   JWT validate   ┌────────────────┐  /v1/data/allow             │
│   │  API Gateway │ ───────────────► │   API Service  │ ──────────────►┌──────────┐│
│   │  (Envoy)     │                  │   (FastAPI)    │                 │   OPA    ││
│   └──────────────┘                  └───────┬────────┘ ◄──────────────│  Engine  ││
│          │ rate-limit                       │ SVID req │ allow/deny    └──────────┘│
│          │ TLS term                         ▼          │ + reasons                 │
│          │                         ┌────────────────┐  │                           │
│          │                         │ Identity Broker│──┘    ┌────────────────────┐ │
│          │                         │   (SPIRE)      │       │   Decision Log     │ │
│          │                         └────────────────┘       │   (Azure Monitor)  │ │
│          │                                  │ SVID issued   └────────────────────┘ │
│          │                                  ▼                                      │
│          │                         ┌────────────────┐  tool ACL  ┌──────────────┐ │
│          │                         │ Agent Runtime  │ ──────────►│   RAG Core   │ │
│          │                         │ (sandboxed)    │            │   Pipeline   │ │
│          │                         └───────┬────────┘            └──────┬───────┘ │
│          │                                 │ mTLS / SVID               │ pgvector │
│          │                                 ▼                            ▼          │
│          │                         ┌────────────────┐         ┌────────────────┐  │
│          │                         │  Azure OpenAI  │         │  PostgreSQL    │  │
│          │                         │  (proxied)     │         │  (pgvector)    │  │
│          │                         └────────────────┘         └────────────────┘  │
│          │                                                                         │
│          │    ┌──────────────────────────────────────────────────────────────────┐ │
│          └───►│  OTEL Collector (PII scrub → Azure Monitor / App Insights)       │ │
│               └──────────────────────────────────────────────────────────────────┘ │
│                                                                                    │
│   ┌────────────────────────────────────────────────────────────────────────────┐   │
│   │  External Secrets Operator ──── WorkloadIdentity ──► Azure Key Vault       │   │
│   └────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. STRIDE Analysis

### 5.1 API Gateway

| STRIDE | Threat | Likelihood | Impact | Mitigations | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Attacker presents forged JWT from another tenant | Medium | High | Audience (`aud`) claim validation; issuer pinning to Entra tenant ID; short token TTL (15 min) | Low |
| **Tampering** | HTTP header injection to bypass downstream auth checks | Low | High | Strict header allow-listing; NGINX `proxy_pass` strips non-allowlisted headers; WAF rule set | Low |
| **Repudiation** | Client denies making a specific request | Low | Medium | Request ID injected at gateway; correlated with decision log entry; immutable audit log in Azure Monitor | Very Low |
| **Information Disclosure** | Error messages reveal internal topology | Medium | Medium | Generic error responses for 5xx; internal details only in structured logs (not response body) | Low |
| **Denial of Service** | Request flood exhausts upstream capacity | High | High | Rate limiting per principal (token bucket); connection limits; Azure DDoS Protection Standard | Medium |
| **Elevation of Privilege** | Path traversal bypasses route-level authorization | Low | Critical | Normalized URL paths before routing; Kyverno policy blocks privileged container escape vectors | Low |

### 5.2 OPA Policy Engine

| STRIDE | Threat | Likelihood | Impact | Mitigations | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Malicious caller pretends to be trusted service to query OPA | Low | Critical | OPA API bound to cluster-internal service; mTLS between caller and OPA; Kubernetes NetworkPolicy restricts callers | Very Low |
| **Tampering** | Bundle poisoning — attacker injects malicious Rego policy | Low | Critical | Bundle signed with cosign; signature verified at load time; bundle served from private ACR; GitOps immutable history | Low |
| **Repudiation** | Policy evaluation results disputed after incident | Low | High | Decision log written to append-only Azure Monitor; decision_id correlates request to evaluation context | Very Low |
| **Information Disclosure** | OPA decision log contains sensitive principal or resource data | Medium | High | Decision log fields allowlisted; secrets/tokens stripped from logged input; PII scrubbing in OTEL pipeline | Low |
| **Denial of Service** | Expensive Rego queries cause evaluation timeout, blocking requests | Low | High | Policy unit tests enforce eval time < 50ms; circuit breaker in API service; OPA memory limits enforced | Low |
| **Elevation of Privilege** | Rego `data` document contains elevated grants injected via external data | Low | Critical | External data sources require explicit allowlisting; bundle content reviewed in PR; no dynamic data injection from untrusted sources | Low |

### 5.3 Identity Broker (SPIRE)

| STRIDE | Threat | Likelihood | Impact | Mitigations | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Workload impersonates another workload to obtain SVID | Low | Critical | SPIRE uses Kubernetes workload attestation (pod UID, namespace, service account); attestation policy requires namespace + SA + pod label match | Very Low |
| **Tampering** | SPIRE agent binary replaced on node | Very Low | Critical | Node image signed; Kyverno enforce signed images; read-only rootfs for SPIRE agent pod; Azure Defender for Containers node scanning | Very Low |
| **Repudiation** | SVID issuance events not auditable | Low | Medium | SPIRE audit log written to stdout captured by OTEL; correlated with Entra sign-in logs by timestamp + principal | Very Low |
| **Information Disclosure** | Private key material for SVID signing leaked | Very Low | Critical | Signing keys stored in Azure Key Vault HSM; keys never leave HSM boundary; SPIRE uses KMS plugin | Very Low |
| **Denial of Service** | SPIRE server unavailable blocks all SVID issuance | Low | High | SPIRE server runs in HA mode (3 replicas); PDB prevents simultaneous eviction; health probe restarts unhealthy pods | Low |
| **Elevation of Privilege** | SPIRE agent running with excessive privileges allows node escape | Very Low | Critical | SPIRE agent runs as non-root; drops all capabilities; read-only rootfs; seccomp profile applied | Very Low |

### 5.4 RAG Pipeline

| STRIDE | Threat | Likelihood | Impact | Mitigations | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Unauthenticated caller retrieves documents from RAG | Low | High | RAG endpoint requires valid SVID in mTLS handshake; caller identity checked against OPA before query | Very Low |
| **Tampering** | Adversarial document injected into corpus to poison agent context | Medium | High | Document ingestion pipeline validates source hash; admin approval required for new documents; content scanning for prompt injection patterns | Medium |
| **Repudiation** | Agent denies retrieving a specific document that influenced decision | Low | Medium | Retrieval events logged with document IDs and relevance scores; correlated with agent session ID | Very Low |
| **Information Disclosure** | Agent retrieves documents outside its authorized scope | Medium | High | Document-level ACL enforced before returning results; OPA evaluates `doc.classification <= agent.clearance` | Low |
| **Denial of Service** | Expensive vector similarity search blocks pipeline | Low | Medium | Query timeout enforced at 2s; pgvector index tuned with HNSW; connection pool limits prevent exhaustion | Low |
| **Elevation of Privilege** | Prompt injection in retrieved document causes agent to bypass constraints | Medium | High | Retrieved text treated as data, not instructions; system prompt instructs model to reject tool call instructions in context | Medium |

### 5.5 Agent Runtime

| STRIDE | Threat | Likelihood | Impact | Mitigations | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Agent session token reused after expiry to continue operations | Low | High | Session tokens include `exp` claim; token expiry enforced at runtime; revocation list checked per request | Very Low |
| **Tampering** | Agent modifies its own allowed_tools list at runtime | Very Low | Critical | `allowed_tools` stored in OPA data bundle, not in agent process memory; runtime reads list from OPA at each tool call | Very Low |
| **Repudiation** | Agent denies having invoked a specific tool | Very Low | High | Every tool invocation logged with session_id, tool_name, args_hash, and SVID before execution; logs immutable | Very Low |
| **Information Disclosure** | Agent leaks secrets from environment to external tool | Medium | High | Secrets not injected as env vars; accessed only via mounted secret volumes with runtime redaction; OTEL scrubs secrets from logs | Medium |
| **Denial of Service** | Runaway agent consumes all CPU/memory on node | Medium | High | cgroups CPU and memory limits enforced; OOM kill terminates offending pod; HPA scales to absorb legitimate load spikes | Low |
| **Elevation of Privilege** | Agent exploits container escape via kernel vulnerability | Very Low | Critical | gVisor (runsc) runtime sandbox isolates agent from host kernel; Kyverno disallows privileged + hostPath; Azure Defender runtime detection | Low |

---

## 6. Top 10 Mitigations Summary

1. **mTLS everywhere**: All inter-service communication uses mutual TLS with SPIFFE SVIDs. No plaintext east-west traffic is permitted. NetworkPolicy enforces this at the network layer in addition to the application layer.

2. **OPA as central policy engine**: All authorization decisions — API access, tool calls, document retrieval, JIT access grants — flow through OPA. Policies are version-controlled in Git and deployed via signed bundles.

3. **Signed container images**: All container images are signed with Sigstore cosign keyless signing from GitHub Actions. Kyverno ClusterPolicy enforces image signature verification before pod admission.

4. **Workload identity (no long-lived credentials)**: Services use Azure Workload Identity for Key Vault access and Azure API calls. No service account keys, connection strings, or API keys exist in code or environment variables.

5. **SPIFFE/SVID workload attestation**: The SPIRE server issues short-lived (1h TTL) X.509 SVIDs to workloads based on Kubernetes attestation. Workload identity is cryptographically bound to the pod's service account and namespace.

6. **Prompt injection defense in RAG**: Retrieved document content is explicitly marked as data context in the system prompt. The model is instructed to reject any tool call instructions embedded in retrieved text. Input validation scans for known injection patterns.

7. **PII scrubbing in telemetry pipeline**: The OTEL collector applies regex-based redaction for Bearer tokens, email addresses, and UUIDs before exporting to Azure Monitor. Sensitive fields are allowlisted in the decision log output.

8. **Kyverno pod security policies**: ClusterPolicies enforce no privileged containers, no host namespaces, no hostPath volumes, required resource limits, and required image signatures across the `agentic-zero-trust` namespace.

9. **Immutable audit trail**: Policy decisions, tool invocations, SVID issuances, and secret accesses are written to append-only Azure Monitor Log Analytics with 90-day retention. Decision logs include full input context for forensic reconstruction.

10. **gVisor container sandbox**: Agent Runtime pods use the gVisor (runsc) runtime class, which provides a user-space kernel between the container and the host OS kernel, isolating container escape attempts from affecting the underlying node.

---

## 7. Residual Risks

### Risk 1: Prompt Injection via Retrieved Documents
**Description:** Despite input validation and system-prompt defenses, a sufficiently sophisticated adversarial document in the corpus could influence model behavior in unintended ways.  
**Likelihood:** Low | **Impact:** High  
**Justification:** Accepted because (a) mitigation significantly reduces the attack surface, (b) all tool calls are still gated by OPA regardless of model behavior, and (c) the blast radius is limited to the agent's declared scope. Monitored via faithfulness eval metrics.

### Risk 2: Zero-Day in gVisor Sandbox
**Description:** A kernel vulnerability in the gVisor runtime could allow a container to escape to the host node.  
**Likelihood:** Very Low | **Impact:** Critical  
**Justification:** Accepted because (a) gVisor itself provides substantial isolation from the host kernel, (b) Azure Defender for Containers provides runtime detection, and (c) AKS nodes are auto-patched on a weekly cadence. Full kernel isolation would require confidential computing (future roadmap).

### Risk 3: OPA Bundle Compromise via Supply Chain Attack
**Description:** An attacker with write access to the bundle repository could inject a malicious policy that broadens agent permissions.  
**Likelihood:** Very Low | **Impact:** Critical  
**Justification:** Accepted because (a) the bundle repository has branch protection requiring two approvals, (b) bundles are signed and verified at load time, and (c) the OPA deployment is monitored for unexpected policy changes via AlertRule in Azure Monitor.

### Risk 4: Entra ID Tenant-Level Misconfiguration
**Description:** A misconfigured Conditional Access Policy in Azure Entra ID could allow tokens to be issued without MFA or from non-compliant devices.  
**Likelihood:** Low | **Impact:** High  
**Justification:** Accepted because Entra ID is a managed service outside direct control of the platform team. Mitigated by periodic Conditional Access Policy reviews and alerting on sign-ins from non-compliant devices (KQL alert in sentinel).

### Risk 5: Denial-of-Service Against SPIRE Server During Incident Response
**Description:** An attacker who can generate high SVID issuance load could exhaust SPIRE server capacity during a time-sensitive incident, preventing credential rotation.  
**Likelihood:** Low | **Impact:** Medium  
**Justification:** Accepted because (a) existing SVIDs remain valid for their TTL (1h), providing a grace window, (b) SPIRE HA configuration provides resilience, and (c) the break-glass procedure allows emergency cluster-admin access that bypasses SPIRE. Monitoring alert fires if SVID issuance latency exceeds 500ms P95.

---

## 8. Review Schedule

| Review Type | Frequency | Owner | Trigger Events |
|---|---|---|---|
| Routine threat model review | Quarterly | Security Architecture Team | Calendar schedule |
| Post-incident update | Within 5 business days of security incident | Incident Commander + Security Architect | Any P1/P2 security incident |
| New component review | Before production deployment | Security Architecture Team | Any new service or integration added |
| External penetration test | Annual | Third-party security firm | Contract renewal cycle |
| Regulatory review | Annual | Compliance Team + Security Architect | Compliance audit cycle |
| Red team exercise | Annual | Internal Red Team | Annual security calendar |

**Next scheduled review:** 2024-09-01  
**Last reviewed:** 2024-06-01  
**Document owner:** Security Architecture Team  
**Approvers:** CISO, Head of Platform Engineering  
