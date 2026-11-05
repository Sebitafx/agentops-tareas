CREATE TABLE agentops_turns (
    seq BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES agentops_inbox ON DELETE CASCADE,
    lease UUID,
    claimed_at TIMESTAMPTZ,
    answer TEXT
);

-- Microdólares reservados. El presupuesto de desarrollo deja $5 para la demo.
CREATE TABLE agentops_ai_budget (
    singleton BOOLEAN PRIMARY KEY CHECK (singleton),
    reserved BIGINT NOT NULL DEFAULT 0 CHECK (reserved >= 0)
);
INSERT INTO agentops_ai_budget(singleton) VALUES (true);
