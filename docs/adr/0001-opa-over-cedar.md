# ADR 0001: Use OPA Over Cedar for Policy Engine

**Status:** Accepted  
**Date:** 2024-01-15  
**Deciders:** Architecture Team, Security Team, Platform Engineering Lead  
**Supersedes:** None  
**Superseded by:** None  

---

## Context

The Agentic Zero Trust Platform requires a centralized policy decision point (PDP) capable of making authorization decisions for AI agents in real time. Every agent action — tool invocations, data retrievals, API calls, and JIT access requests — must be evaluated against a policy that considers principal identity, resource sensitivity, agent posture score, delegation chain depth, and environmental context. The policy engine must handle decisions with sub-100ms P95 latency under peak load and must be auditable, version-controlled, and deployable in a GitOps workflow.

We evaluated policy engines against three primary criteria: (1) expressiveness — can the language represent our complex, context-dependent authorization logic without excessive boilerplate; (2) ecosystem maturity — is there production-grade Kubernetes integration, tooling, and community support; and (3) operational fit — does the engine integrate naturally with our Azure-first, CNCF-centric infrastructure. The two leading candidates were Open Policy Agent (OPA) and Amazon Cedar. A brief investigation of Google Zanzibar-inspired systems (e.g., OpenFGA, SpiceDB) was also conducted but deprioritized due to their graph-centric model being a mismatch for our hierarchical resource model.

This decision has significant downstream implications because the policy engine is the root of trust for all runtime authorization decisions. Changing it after production deployment would require rewriting all policy rules, re-testing all authorization flows, and replacing the Kubernetes admission control integration. The decision must therefore be stable and well-justified before implementation begins.

---

## Decision

Use **Open Policy Agent (OPA)** with **Rego** as the policy evaluation engine for all authorization decisions in the Agentic Zero Trust Platform. OPA will be deployed as a standalone service within the cluster, called over its HTTP API by all platform services. Kyverno (also OPA-based) will handle Kubernetes admission control. The OPA bundle server will be hosted in the platform's private Azure Container Registry and signed with cosign for integrity verification.

---

## Rationale

### Why OPA wins on ecosystem maturity

OPA is a CNCF graduated project, the highest maturity designation, indicating long-term stability and broad enterprise adoption. The OPA Gatekeeper project provides a production-ready Kubernetes admission controller with extensive documentation, examples, and community policy libraries. The `conftest` tooling enables policy unit testing in CI, and the `opa eval` CLI supports local development and debugging. This mature toolchain significantly reduces the operational burden of managing policies at scale.

### Why Rego fits our data model

Our authorization input documents are JSON objects containing principal claims, resource descriptors, and contextual signals. Rego is designed from the ground up to query and transform JSON documents, making it a natural fit. The policy logic we need — evaluating posture thresholds, checking delegation depth, computing effective permissions from multiple data sources — maps cleanly to Rego rules without the impedance mismatch that would occur with Cedar's resource-oriented model.

### Why Cedar is not the right choice here

Cedar was designed primarily for authorization in AWS services and optimized for the Cedar policy language's static analysis properties (type-checking and formal verification). While these properties are valuable, they come at the cost of expressiveness: Cedar policies are intentionally constrained to a subset of authorization patterns expressible in Rego. Our use case requires dynamic data joins (posture signals from an external source combined with static policy data), which is straightforward in Rego but awkward in Cedar. Additionally, Cedar's tooling and community are primarily oriented around AWS IAM-like patterns, and there is no mature Kubernetes admission controller integration.

### Why not Zanzibar-style systems (OpenFGA, SpiceDB)

Zanzibar-style systems model authorization as a relationship graph and excel at fine-grained, user-object relationship queries (e.g., "does user X have editor relationship to document Y via group membership"). Our authorization model is not primarily relationship-based — it is attribute-based (ABAC), combining principal attributes, resource sensitivity classifications, environmental context, and computed posture scores. Mapping our model to a relationship graph would require significant schema contortion and would make policy logic less readable and harder to audit.

---

## Consequences

### Positive

1. **Mature Kubernetes integration via OPA Gatekeeper**: Admission control for all platform Pods, Services, and other resources is handled by a battle-tested, CNCF-backed project with extensive policy library coverage.

2. **JSON-native policy language**: Rego's ability to query and join JSON documents means our authorization input objects map directly to policy input without transformation. Policy rules are readable and reviewable by engineers without specialized training.

3. **Built-in policy testing framework**: `opa test` enables comprehensive unit testing of every policy rule, supporting a policy-as-code workflow where every policy change is tested in CI before deployment.

4. **GitOps-compatible bundle distribution**: OPA's bundle mechanism allows policies to be version-controlled in Git, signed with cosign, and distributed to OPA instances via an HTTP bundle server. This integrates directly with ArgoCD and the existing GitOps workflow.

5. **Decision logging for audit compliance**: OPA's built-in decision log stream captures every evaluation decision with the full input context, supporting forensic investigation and compliance reporting without additional instrumentation.

### Negative

1. **Rego has a learning curve**: Rego's logic programming style is unfamiliar to engineers accustomed to imperative languages. Policy reviews require reviewers who understand Rego semantics, particularly around partial rules and the open-world assumption for undefined values.

2. **Performance at high throughput requires caching**: OPA's HTTP evaluation API introduces network latency. At high request rates, the platform must cache recent decisions (e.g., in Redis with short TTL) to meet the P95 < 100ms SLO. This adds operational complexity.

3. **No formal verification of policies**: Unlike Cedar, Rego does not support static type-checking or formal verification of policy correctness. Policy bugs must be caught through testing and review rather than compile-time analysis.

---

## Alternatives Considered

### Amazon Cedar

**Pros:** Formal verification support (type safety, policy analysis); designed for fine-grained authorization; AWS has open-sourced the Cedar SDK for non-AWS use.  
**Cons:** No mature Kubernetes admission controller integration; optimized for AWS IAM-like resource models; less expressive for attribute-based policies with dynamic data joins; smaller community and fewer enterprise case studies outside AWS; tooling is less mature for non-AWS deployment contexts.  
**Verdict:** Rejected. The ecosystem immaturity outside AWS and the expressiveness limitation for our ABAC use case outweigh the formal verification benefit.

### Google Zanzibar (OpenFGA / SpiceDB)

**Pros:** Excellent at fine-grained relationship-based authorization; Google-scale production validation via Zanzibar paper; OpenFGA and SpiceDB are well-maintained open-source implementations.  
**Cons:** Relationship graph model is a poor fit for ABAC; would require mapping all agent attributes and resource classifications to relationship triples; no native Kubernetes admission controller integration; adds complexity for relatively little benefit given our non-graph authorization model.  
**Verdict:** Rejected. The authorization model mismatch is fundamental and would result in complex, hard-to-maintain policy schemas.

---

## Related Decisions

- **ADR 0002**: Azure Workload Identity + SPIFFE/SPIRE for workload identity (OPA policy inputs rely on SPIFFE SVIDs as principal identifiers)
- **ADR 0003**: PostgreSQL with pgvector for agent state and document store (OPA bundle data sourced from this store)

---

## Review Notes

This ADR was reviewed by the Architecture Team on 2024-01-15 and approved with no dissenting votes. The decision will be revisited if Cedar's Kubernetes integration matures to production-grade status or if OPA performance characteristics prove insufficient under production load. The next scheduled review is 2025-01-15.
