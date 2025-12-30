-- Migration: Add user profiles and conversation tracking
-- This allows tracking both authenticated and anonymous users
-- Run this after init.sql or on existing database

-- ============================================
-- USER PROFILES TABLE
-- Tracks both authenticated and anonymous users
-- ============================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Profile type: 'authenticated' or 'anonymous'
    profile_type VARCHAR(20) NOT NULL DEFAULT 'anonymous',
    
    -- For authenticated users
    username VARCHAR(255),
    phone_number VARCHAR(50),
    email VARCHAR(255),
    
    -- For anonymous users - fingerprinting data
    anonymous_id VARCHAR(255), -- Browser fingerprint, device ID, etc.
    
    -- Profile metadata extracted from conversations
    profile_metadata JSONB DEFAULT '{}', -- {"name": "John", "preferences": {...}, "topics": [...]}
    
    -- Conversation stats
    total_sessions INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    last_seen_at TIMESTAMP,
    
    -- Authentication status
    is_authenticated BOOLEAN DEFAULT FALSE,
    authenticated_at TIMESTAMP,
    
    -- Linking: anonymous profiles can be merged with authenticated ones
    merged_into_profile_id UUID REFERENCES user_profiles(id),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure either authenticated data or anonymous_id exists
    CONSTRAINT check_profile_identity CHECK (
        (profile_type = 'authenticated' AND (username IS NOT NULL OR phone_number IS NOT NULL OR email IS NOT NULL))
        OR
        (profile_type = 'anonymous' AND anonymous_id IS NOT NULL)
    )
);

-- Indexes for fast lookups
CREATE INDEX idx_profiles_username ON user_profiles (username) WHERE username IS NOT NULL;
CREATE INDEX idx_profiles_phone ON user_profiles (phone_number) WHERE phone_number IS NOT NULL;
CREATE INDEX idx_profiles_anonymous_id ON user_profiles (anonymous_id) WHERE anonymous_id IS NOT NULL;
CREATE INDEX idx_profiles_type ON user_profiles (profile_type);
CREATE INDEX idx_profiles_last_seen ON user_profiles (last_seen_at);

-- ============================================
-- UPDATE AGENT_SESSIONS TABLE
-- Add profile_id to link sessions to user profiles
-- ============================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'agent_sessions' AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE agent_sessions 
        ADD COLUMN profile_id UUID REFERENCES user_profiles(id);
        
        CREATE INDEX idx_sessions_profile ON agent_sessions (profile_id);
    END IF;
END $$;

-- ============================================
-- CONVERSATION SUMMARIES TABLE
-- Stores AI-generated summaries of conversations
-- ============================================
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    
    -- Summary content
    summary TEXT NOT NULL,
    
    -- Key information extracted from conversation
    extracted_info JSONB DEFAULT '{}', -- {"name": "John", "intent": "check balance", "topics": [...]}
    
    -- Conversation metrics
    message_count INT DEFAULT 0,
    duration_seconds INT, -- How long the conversation lasted
    
    -- Sentiment and quality
    sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
    resolution_status VARCHAR(50), -- 'resolved', 'escalated', 'incomplete'
    
    -- Topics discussed
    topics TEXT[], -- Array of topics: ['balance check', 'transfer', 'card issue']
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_summaries_session ON conversation_summaries (session_id);
CREATE INDEX idx_summaries_profile ON conversation_summaries (profile_id);
CREATE INDEX idx_summaries_created ON conversation_summaries (created_at);
CREATE INDEX idx_summaries_topics ON conversation_summaries USING GIN (topics);

-- ============================================
-- UPDATE TRIGGERS
-- ============================================

-- Trigger to update user_profiles.updated_at
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to merge anonymous profile into authenticated one
CREATE OR REPLACE FUNCTION merge_profiles(
    p_anonymous_profile_id UUID,
    p_authenticated_profile_id UUID
) RETURNS VOID AS $$
BEGIN
    -- Update all sessions to point to authenticated profile
    UPDATE agent_sessions 
    SET profile_id = p_authenticated_profile_id 
    WHERE profile_id = p_anonymous_profile_id;
    
    -- Update all summaries to point to authenticated profile
    UPDATE conversation_summaries 
    SET profile_id = p_authenticated_profile_id 
    WHERE profile_id = p_anonymous_profile_id;
    
    -- Merge stats
    UPDATE user_profiles 
    SET 
        total_sessions = total_sessions + (SELECT total_sessions FROM user_profiles WHERE id = p_anonymous_profile_id),
        total_messages = total_messages + (SELECT total_messages FROM user_profiles WHERE id = p_anonymous_profile_id)
    WHERE id = p_authenticated_profile_id;
    
    -- Mark anonymous profile as merged
    UPDATE user_profiles 
    SET merged_into_profile_id = p_authenticated_profile_id 
    WHERE id = p_anonymous_profile_id;
    
    RAISE NOTICE 'Successfully merged profile % into %', p_anonymous_profile_id, p_authenticated_profile_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update profile stats when session ends
CREATE OR REPLACE FUNCTION update_profile_stats_on_session_end()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'ended' AND OLD.status != 'ended' THEN
        UPDATE user_profiles 
        SET 
            total_sessions = total_sessions + 1,
            total_messages = total_messages + NEW.message_count,
            last_seen_at = NEW.ended_at
        WHERE id = NEW.profile_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profile_on_session_end
    AFTER UPDATE ON agent_sessions
    FOR EACH ROW
    WHEN (NEW.status = 'ended' AND OLD.status != 'ended')
    EXECUTE FUNCTION update_profile_stats_on_session_end();

-- ============================================
-- MIGRATION COMPLETE MESSAGE
-- ============================================
DO $$ 
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'User Profiles Migration Complete!';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Added tables:';
    RAISE NOTICE '  - user_profiles (authenticated + anonymous users)';
    RAISE NOTICE '  - conversation_summaries (AI-generated summaries)';
    RAISE NOTICE 'Updated tables:';
    RAISE NOTICE '  - agent_sessions (added profile_id)';
    RAISE NOTICE 'Added functions:';
    RAISE NOTICE '  - merge_profiles() - merge anonymous -> authenticated';
    RAISE NOTICE '  - Auto-update profile stats on session end';
    RAISE NOTICE '=================================================';
END $$;
