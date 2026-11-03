CREATE TABLE agentops_inbox (
    message_id TEXT PRIMARY KEY,
    phone_number_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'processed', 'failed'))
);
CREATE INDEX agentops_inbox_pending ON agentops_inbox (received_at) WHERE state = 'pending';

CREATE TABLE agentops_delivery_status (
    message_id TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, status, occurred_at)
);
