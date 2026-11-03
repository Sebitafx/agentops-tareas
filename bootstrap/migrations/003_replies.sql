CREATE TABLE agentops_jobs (
    id UUID PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES agentops_inbox(message_id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'received' CHECK (state IN (
        'received', 'needs_input', 'queued', 'running', 'validating', 'pr_open',
        'merged', 'deploying', 'succeeded', 'failed', 'blocked'
    )),
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE agentops_outbox (
    id UUID PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES agentops_inbox(message_id) ON DELETE CASCADE,
    body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 4096),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN (
        'pending', 'sending', 'sent', 'failed', 'uncertain', 'expired'
    )),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    provider_message_id TEXT UNIQUE,
    delivery_status TEXT,
    delivery_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX agentops_outbox_pending ON agentops_outbox(next_attempt_at)
    WHERE state = 'pending';
