CREATE TABLE IF NOT EXISTS ai_messages (
    id SERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls JSONB,
    tool_results JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_messages_thread_id ON ai_messages (thread_id);

CREATE TABLE IF NOT EXISTS ai_sessions (
    id SERIAL PRIMARY KEY,
    thread_id TEXT UNIQUE NOT NULL,
    language VARCHAR(10),
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_thread_id ON ai_sessions (thread_id);
