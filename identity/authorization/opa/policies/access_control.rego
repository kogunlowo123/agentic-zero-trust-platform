package zerotrust.access_control

import future.keywords.if
import future.keywords.in

# Action permission matrix per tier
# T0: read only
# T1: read, list, write
# T2: read, list, write, execute, admin

default can_perform := false

# T2 agents can perform any action
can_perform if {
    input.principal.tier == "T2"
}

# T1 agents can perform read, list, write operations
can_perform if {
    input.principal.tier == "T1"
    input.action in {"read", "list", "write"}
}

# T0 agents can only perform read and list
can_perform if {
    input.principal.tier == "T0"
    input.action in {"read", "list"}
}

# Resource-specific restrictions
# Admin actions require T2 regardless of what tier_ordinal math says
admin_requires_t2 if {
    input.action == "admin"
    input.principal.tier != "T2"
}

# Execute requires T1 or higher
execute_requires_t1 if {
    input.action == "execute"
    tier_ordinal[input.principal.tier] < 1
}

tier_ordinal := {
    "T0": 0,
    "T1": 1,
    "T2": 2,
}

# Reason for access control denial
access_deny_reasons[reason] {
    not can_perform
    reason := sprintf("ACTION_NOT_PERMITTED_FOR_TIER: action=%v tier=%v", [input.action, input.principal.tier])
}

access_deny_reasons[reason] {
    admin_requires_t2
    reason := "ADMIN_ACTION_REQUIRES_T2_TIER"
}

access_deny_reasons[reason] {
    execute_requires_t1
    reason := "EXECUTE_ACTION_REQUIRES_T1_OR_HIGHER"
}
