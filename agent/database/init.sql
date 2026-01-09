-- Database initialization script for Voice AI Agent
-- Creates tables for agent instructions, sessions, conversations, and RAG documents
-- Requires PostgreSQL 13+ with pgvector extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Agent Instructions table
-- Stores system prompts and configurations
CREATE TABLE IF NOT EXISTS agent_instructions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    instructions TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    is_local_mode BOOLEAN DEFAULT FALSE,
    initial_greeting TEXT,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookup of active instructions
CREATE INDEX idx_agent_instructions_active ON agent_instructions (is_active, is_local_mode) WHERE is_active = TRUE;

-- Agent Sessions table
-- One row per user conversation session
CREATE TABLE IF NOT EXISTS agent_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id VARCHAR(255) NOT NULL,
    participant_id VARCHAR(255) NOT NULL,
    agent_instruction_id INT REFERENCES agent_instructions(id),
    llm_provider VARCHAR(50) NOT NULL DEFAULT 'ollama',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    context JSONB DEFAULT '{}',
    message_count INT DEFAULT 0,
    duration_seconds INT, -- Total conversation duration in seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

-- Indexes for session lookups
CREATE INDEX idx_sessions_room ON agent_sessions (room_id);
CREATE INDEX idx_sessions_status ON agent_sessions (status);
CREATE INDEX idx_sessions_activity ON agent_sessions (last_activity);

-- Conversation Messages table
-- Stores all messages in conversations
CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient conversation history retrieval
CREATE INDEX idx_conversation_session ON conversation_messages (session_id, created_at);

-- RAG Documents table
-- Stores document chunks with vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS rag_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    total_chunks INT NOT NULL DEFAULT 1,
    embedding vector(768), -- 768 dimensions for nomic-embed-text:latest
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (filename, chunk_index)
);

-- Indexes for fast vector similarity search
CREATE INDEX idx_rag_filename ON rag_documents (filename);
CREATE INDEX idx_rag_embedding ON rag_documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- User Profiles table
-- Tracks both authenticated and anonymous users
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_type VARCHAR(20) NOT NULL DEFAULT 'anonymous',
    username VARCHAR(255),
    phone_number VARCHAR(50),
    email VARCHAR(255),
    anonymous_id VARCHAR(255),
    profile_metadata JSONB DEFAULT '{}',
    total_sessions INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    last_seen_at TIMESTAMP,
    is_authenticated BOOLEAN DEFAULT FALSE,
    authenticated_at TIMESTAMP,
    merged_into_profile_id UUID REFERENCES user_profiles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_profile_identity CHECK (
        (profile_type = 'authenticated' AND (username IS NOT NULL OR phone_number IS NOT NULL OR email IS NOT NULL))
        OR
        (profile_type = 'anonymous' AND anonymous_id IS NOT NULL)
    )
);

CREATE INDEX idx_profiles_username ON user_profiles (username) WHERE username IS NOT NULL;
CREATE INDEX idx_profiles_anonymous ON user_profiles (anonymous_id) WHERE anonymous_id IS NOT NULL;
CREATE INDEX idx_profiles_type ON user_profiles (profile_type);

-- Link sessions to profiles
ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS profile_id UUID REFERENCES user_profiles(id);
CREATE INDEX IF NOT EXISTS idx_sessions_profile ON agent_sessions (profile_id);

-- Conversation Summaries table
-- Stores AI-generated summaries of conversations
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES user_profiles(id),
    summary TEXT NOT NULL,
    key_topics TEXT[],
    sentiment VARCHAR(20),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_summaries_session ON conversation_summaries (session_id);
CREATE INDEX idx_summaries_profile ON conversation_summaries (profile_id);

-- System Configuration table
-- Key-value store for system-wide settings
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default agent instructions from prompt.py
-- You can update these after setup
INSERT INTO agent_instructions (name, instructions, is_active, is_local_mode, initial_greeting, language)
VALUES (
    'Default Local Mode',
    'You are Batsi, a friendly voice assistant for TN CyberTech Bank.

STYLE:
- Be conversational and friendly
- Give SHORT responses (1-2 sentences)
- Use search_web for current events or information

BANKING TRANSACTIONS (REQUIRE LOGIN):
When user wants to: check balance, make transfer, get statement, cardless withdrawal or bank balance or account info
→ Ask for username and PIN, then call authenticate_bank(username, password)

GENERAL CHAT (NO LOGIN NEEDED):
When user is: chatting, asking questions, wanting information
→ Just respond naturally or use search_web',
    TRUE,
    TRUE,
    'Hello! I''m Batsi from TN CyberTech Bank. How can I help you today?',
    'en'
) ON CONFLICT DO NOTHING;

-- Insert system configuration defaults
INSERT INTO system_config (key, value, description)
VALUES 
    ('max_concurrent_sessions', '30', 'Maximum number of concurrent user sessions'),
    ('session_timeout_minutes', '30', 'Minutes of inactivity before session expires'),
    ('rag_enabled', 'true', 'Enable RAG document retrieval'),
    ('embedding_model', 'all-MiniLM-L6-v2', 'Sentence transformer model for embeddings')
ON CONFLICT (key) DO NOTHING;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to auto-update updated_at
CREATE TRIGGER update_agent_instructions_updated_at
    BEFORE UPDATE ON agent_instructions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rag_documents_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_config_updated_at
    BEFORE UPDATE ON system_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust username as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Display initialization summary
SELECT 
    'Database initialized successfully!' as status,
    (SELECT COUNT(*) FROM agent_instructions) as agent_instructions,
    (SELECT COUNT(*) FROM system_config) as system_configs;
