-- depends: 0001.ai-initial-schema
ALTER TABLE ai_messages ADD COLUMN IF NOT EXISTS attachments JSONB;
