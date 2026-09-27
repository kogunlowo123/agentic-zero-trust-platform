-- Session Ledger Schema
-- Immutable audit log of all policy decisions and agent actions
-- Stored in Azure PostgreSQL Flexible Server

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main session ledger table (append-only, no updates or deletes)
CREATE TABLE IF NOT EXISTS session_ledger (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      VARCHAR(255)    NOT NULL,
    principal       VARCHAR(255)    NOT NULL,
    agent_id        VARCHAR(255)    NOT NULL,
    action          VARCHAR(255)    NOT NULL,
    resource        VARCHAR(255),
    resource_sensitivity VARCHAR(50) CHECK (resource_sensitivity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    decision        VARCHAR(50)     NOT NULL CHECK (decision IN ('allow', 'deny', 'abstain')),
    decision_id     VARCHAR(255),
    opa_reasons     TEXT[]          DEFAULT '{}',
    posture_score   FLOAT           CHECK (posture_score IS NULL OR (posture_score >= 0 AND posture_score <= 100)),
    agent_tier      VARCHAR(10)     CHECK (agent_tier IN ('T0', 'T1', 'T2')),
    delegation_depth INTEGER        DEFAULT 0,
    svid_hash       VARCHAR(64),    -- SHA-256 hash of the SVID (not the SVID itself)
    tool_calls      JSONB           DEFAULT '[]',
    budget_used_usd FLOAT           DEFAULT 0.0,
    latency_ms      INTEGER,
    tenant_id       VARCHAR(255)    DEFAULT 'default',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Prevent modifications to audit log
CREATE RULE no_update_session_ledger AS
    ON UPDATE TO session_ledger DO INSTEAD NOTHING;

CREATE RULE no_delete_session_ledger AS
    ON DELETE TO session_ledger DO INSTEAD NOTHING;

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_session_ledger_principal
    ON session_ledger (principal, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_ledger_session_id
    ON session_ledger (session_id);

CREATE INDEX IF NOT EXISTS idx_session_ledger_created_at
    ON session_ledger (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_ledger_decision
    ON session_ledger (decision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_ledger_agent_id
    ON session_ledger (agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_ledger_tenant_id
    ON session_ledger (tenant_id, created_at DESC);

-- Partial index for deny decisions (most queried for incident response)
CREATE INDEX IF NOT EXISTS idx_session_ledger_denies
    ON session_ledger (principal, created_at DESC)
    WHERE decision = 'deny';

-- JIT Access Requests table
CREATE TABLE IF NOT EXISTS access_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id      VARCHAR(255)    NOT NULL UNIQUE,
    principal       VARCHAR(255)    NOT NULL,
    resource        VARCHAR(255)    NOT NULL,
    action          VARCHAR(100)    NOT NULL,
    justification   TEXT            NOT NULL,
    duration_minutes INTEGER        NOT NULL CHECK (duration_minutes BETWEEN 1 AND 480),
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'denied', 'expired', 'revoked')),
    approved_by     VARCHAR(255),
    denied_reason   TEXT,
    approved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_requests_principal
    ON access_requests (principal, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_access_requests_status
    ON access_requests (status, created_at DESC);

-- Policy violation events (denormalized from session_ledger for fast access)
CREATE TABLE IF NOT EXISTS policy_violations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id     VARCHAR(255)    NOT NULL,
    principal       VARCHAR(255)    NOT NULL,
    resource        VARCHAR(255)    NOT NULL,
    action          VARCHAR(100)    NOT NULL,
    reasons         TEXT[]          NOT NULL DEFAULT '{}',
    posture_score   FLOAT,
    agent_tier      VARCHAR(10),
    acknowledged    BOOLEAN         DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_violations_principal
    ON policy_violations (principal, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_policy_violations_unacked
    ON policy_violations (created_at DESC)
    WHERE acknowledged = FALSE;
