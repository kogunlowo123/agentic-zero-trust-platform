package zerotrust

import future.keywords.if
import future.keywords.in

# Default deny all — zero trust principle: never trust, always verify
default allow := false

# Posture score thresholds per agent tier
posture_threshold := {
    "T0": 50,
    "T1": 70,
    "T2": 90,
}

# Maximum delegation depth per tier
max_depth := {
    "T0": 0,
    "T1": 1,
    "T2": 2,
}

# Resource sensitivity ordinal (used for tier vs sensitivity comparison)
sensitivity_ordinal := {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# Tier ordinal
tier_ordinal := {
    "T0": 0,
    "T1": 1,
    "T2": 2,
}

# --- ALLOW RULE ---
# All conditions must pass for access to be granted

allow if {
    valid_svid
    valid_token
    sufficient_posture
    not delegation_too_deep
    not resource_too_sensitive
}

# --- CONDITION RULES ---

# SVID must be non-empty and from the trusted trust domain
valid_svid if {
    input.principal.svid != ""
    startswith(input.principal.svid, "spiffe://zero-trust.example.com/agent/")
}

# Token must be non-empty and not expired
valid_token if {
    input.principal.token != ""
    input.principal.token_exp > time.now_ns() / 1000000000
}

# Posture score must meet or exceed the threshold for the caller's tier
sufficient_posture if {
    threshold := posture_threshold[input.principal.tier]
    input.posture.score >= threshold
}

# Delegation depth exceeded when caller has delegated beyond their tier's maximum
delegation_too_deep if {
    max := max_depth[input.principal.tier]
    input.principal.delegation_depth > max
}

# Resource sensitivity exceeds what the caller's tier is permitted to access
# T0 (ordinal 0): LOW(1), MEDIUM(2) → tier+2=2, so MEDIUM OK, HIGH(3) denied
# T1 (ordinal 1): LOW, MEDIUM, HIGH → tier+2=3, so HIGH OK, CRITICAL(4) denied
# T2 (ordinal 2): all → tier+2=4, CRITICAL OK
resource_too_sensitive if {
    sens := sensitivity_ordinal[input.resource.sensitivity]
    tier := tier_ordinal[input.principal.tier]
    sens > tier + 2
}

# --- DENY REASONS ---
# Accumulated for audit log — explains why access was denied

deny_reasons[reason] {
    not valid_svid
    reason := "INVALID_SVID"
}

deny_reasons[reason] {
    not valid_token
    reason := "INVALID_OR_EXPIRED_TOKEN"
}

deny_reasons[reason] {
    not sufficient_posture
    threshold := posture_threshold[input.principal.tier]
    reason := sprintf("INSUFFICIENT_POSTURE_SCORE: %v < %v", [input.posture.score, threshold])
}

deny_reasons[reason] {
    delegation_too_deep
    max := max_depth[input.principal.tier]
    reason := sprintf("DELEGATION_DEPTH_EXCEEDED: %v > %v", [input.principal.delegation_depth, max])
}

deny_reasons[reason] {
    resource_too_sensitive
    reason := sprintf(
        "RESOURCE_SENSITIVITY_EXCEEDS_TIER: resource=%v tier=%v",
        [input.resource.sensitivity, input.principal.tier]
    )
}

# --- AUDIT METADATA ---

# Unique decision identifier based on principal + resource + timestamp
decision_id := sprintf("decision-%v-%v", [input.principal.id, time.now_ns()])

# Policy version for audit trail
policy_version := "1.0.0"
