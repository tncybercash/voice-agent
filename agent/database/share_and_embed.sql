-- Share Links and Embed System Migration
-- Creates tables for shareable links and embedding functionality

-- ===========================================
-- SHARE LINKS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS share_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(12) UNIQUE NOT NULL,
    agent_instruction_id INT REFERENCES agent_instructions(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Customization
    custom_greeting TEXT,
    custom_context JSONB DEFAULT '{}',
    branding JSONB DEFAULT '{}',  -- logo_url, accent_color, company_name
    
    -- Access Control
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    max_sessions INT,  -- NULL = unlimited
    allowed_domains TEXT[],  -- NULL = any domain
    require_auth BOOLEAN DEFAULT FALSE,
    
    -- Stats
    total_sessions INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Metadata
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_share_links_code ON share_links (code);
CREATE INDEX idx_share_links_active ON share_links (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_share_links_agent ON share_links (agent_instruction_id);

-- ===========================================
-- SHARE LINK ANALYTICS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS share_link_analytics (
    id SERIAL PRIMARY KEY,
    share_link_id UUID NOT NULL REFERENCES share_links(id) ON DELETE CASCADE,
    session_id UUID REFERENCES agent_sessions(id) ON DELETE SET NULL,
    
    -- Request Info
    visitor_ip VARCHAR(45),
    user_agent TEXT,
    referrer TEXT,
    country VARCHAR(2),
    city VARCHAR(100),
    
    -- Session Info
    messages_count INT DEFAULT 0,
    duration_seconds INT,
    
    -- Event
    event_type VARCHAR(50) NOT NULL DEFAULT 'session_start',  -- session_start, session_end, page_view
    event_data JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_share_link ON share_link_analytics (share_link_id);
CREATE INDEX idx_analytics_session ON share_link_analytics (session_id);
CREATE INDEX idx_analytics_created ON share_link_analytics (created_at);

-- ===========================================
-- EMBED API KEYS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS embed_api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 of actual key
    key_prefix VARCHAR(16) NOT NULL,  -- First 12 chars for identification
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Linked Agent
    agent_instruction_id INT REFERENCES agent_instructions(id) ON DELETE CASCADE,
    
    -- Customization
    custom_greeting TEXT,
    custom_context JSONB DEFAULT '{}',
    branding JSONB DEFAULT '{}',  -- logo_url, accent_color, company_name
    widget_config JSONB DEFAULT '{}',  -- position, theme, size
    
    -- Access Control
    is_active BOOLEAN DEFAULT TRUE,
    allowed_domains TEXT[] NOT NULL,  -- Required for embed
    rate_limit_rpm INT DEFAULT 60,  -- Requests per minute
    max_concurrent_sessions INT DEFAULT 10,
    
    -- Stats
    total_sessions INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Metadata
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embed_keys_hash ON embed_api_keys (key_hash);
CREATE INDEX idx_embed_keys_prefix ON embed_api_keys (key_prefix);
CREATE INDEX idx_embed_keys_active ON embed_api_keys (is_active) WHERE is_active = TRUE;

-- ===========================================
-- EMBED SESSIONS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS embed_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    embed_key_id UUID NOT NULL REFERENCES embed_api_keys(id) ON DELETE CASCADE,
    session_id UUID REFERENCES agent_sessions(id) ON DELETE SET NULL,
    
    -- Origin Info
    origin_domain VARCHAR(255) NOT NULL,
    visitor_id VARCHAR(255),  -- Client-side generated ID
    
    -- Session Info
    messages_count INT DEFAULT 0,
    duration_seconds INT,
    status VARCHAR(20) DEFAULT 'active',  -- active, ended, error
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE INDEX idx_embed_sessions_key ON embed_sessions (embed_key_id);
CREATE INDEX idx_embed_sessions_domain ON embed_sessions (origin_domain);
CREATE INDEX idx_embed_sessions_status ON embed_sessions (status);

-- ===========================================
-- TRIGGERS
-- ===========================================

-- Auto-update updated_at for share_links
CREATE TRIGGER update_share_links_updated_at
    BEFORE UPDATE ON share_links
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-update updated_at for embed_api_keys
CREATE TRIGGER update_embed_keys_updated_at
    BEFORE UPDATE ON embed_api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===========================================
-- FUNCTIONS
-- ===========================================

-- Generate unique share code
CREATE OR REPLACE FUNCTION generate_share_code() 
RETURNS VARCHAR(12) AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
    code VARCHAR(12) := '';
    i INT;
BEGIN
    FOR i IN 1..8 LOOP
        code := code || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    END LOOP;
    RETURN code;
END;
$$ LANGUAGE plpgsql;

-- Increment share link stats
CREATE OR REPLACE FUNCTION increment_share_link_stats(
    p_share_link_id UUID,
    p_messages INT DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    UPDATE share_links
    SET 
        total_sessions = total_sessions + CASE WHEN p_messages = 0 THEN 1 ELSE 0 END,
        total_messages = total_messages + p_messages,
        last_used_at = NOW()
    WHERE id = p_share_link_id;
END;
$$ LANGUAGE plpgsql;

-- Increment embed key stats
CREATE OR REPLACE FUNCTION increment_embed_key_stats(
    p_embed_key_id UUID,
    p_messages INT DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    UPDATE embed_api_keys
    SET 
        total_sessions = total_sessions + CASE WHEN p_messages = 0 THEN 1 ELSE 0 END,
        total_messages = total_messages + p_messages,
        last_used_at = NOW()
    WHERE id = p_embed_key_id;
END;
$$ LANGUAGE plpgsql;

-- Link sessions to share_links
ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS share_link_id UUID REFERENCES share_links(id);
ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS embed_key_id UUID REFERENCES embed_api_keys(id);
CREATE INDEX IF NOT EXISTS idx_sessions_share_link ON agent_sessions (share_link_id);
CREATE INDEX IF NOT EXISTS idx_sessions_embed_key ON agent_sessions (embed_key_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON share_links TO postgres;
GRANT ALL PRIVILEGES ON share_link_analytics TO postgres;
GRANT ALL PRIVILEGES ON embed_api_keys TO postgres;
GRANT ALL PRIVILEGES ON embed_sessions TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Display migration summary
SELECT 
    'Share and Embed tables created successfully!' as status,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('share_links', 'share_link_analytics', 'embed_api_keys', 'embed_sessions')) as tables_created;
