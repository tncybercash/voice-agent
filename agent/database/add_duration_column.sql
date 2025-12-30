-- Add duration tracking to agent_sessions table
ALTER TABLE agent_sessions 
ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;

COMMENT ON COLUMN agent_sessions.duration_seconds IS 'Total conversation duration in seconds';
