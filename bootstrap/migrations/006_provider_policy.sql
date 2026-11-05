ALTER TABLE agentops_jobs ADD COLUMN preferred_provider TEXT
    CHECK (preferred_provider IN ('openai','gemini','groq'));
ALTER TABLE agentops_jobs ADD COLUMN keep_provider BOOLEAN NOT NULL DEFAULT false;
