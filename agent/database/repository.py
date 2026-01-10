"""
Repository layer for database operations.
Provides async CRUD operations for all models.

Note: RAG-related repositories have been removed. Knowledge base queries
will be handled via MCP server tools.
"""
import json
import logging
import hashlib
import secrets
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from .connection import DatabasePool, get_db_pool
from .models import (
    AgentInstruction,
    AgentSession,
    ConversationMessage,
    SystemConfig,
    LLMProvider,
    SessionStatus,
    ShareLink,
    ShareLinkBranding,
    ShareLinkAnalytics,
    EmbedApiKey,
    EmbedSession,
    EmbedSessionStatus,
    WidgetConfig
)

logger = logging.getLogger("repository")


class AgentInstructionRepository:
    """Repository for agent instructions"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def get_all(self) -> list[AgentInstruction]:
        """Get all agent instructions"""
        query = """
            SELECT id, name, instructions, is_active, is_local_mode, 
                   initial_greeting, language, created_at, updated_at
            FROM agent_instructions
            ORDER BY name
        """
        rows = await self.pool.fetch(query)
        return [
            AgentInstruction(
                id=row['id'],
                name=row['name'],
                instructions=row['instructions'],
                is_active=row['is_active'],
                is_local_mode=row['is_local_mode'],
                initial_greeting=row['initial_greeting'],
                language=row['language'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in rows
        ]
    
    async def get_active_instruction(self, is_local_mode: bool = False) -> Optional[AgentInstruction]:
        """Get the currently active agent instruction"""
        query = """
            SELECT id, name, instructions, is_active, is_local_mode, 
                   initial_greeting, language, created_at, updated_at
            FROM agent_instructions
            WHERE is_active = true AND is_local_mode = $1
            ORDER BY updated_at DESC
            LIMIT 1
        """
        row = await self.pool.fetchrow(query, is_local_mode)
        if row:
            return AgentInstruction(
                id=row['id'],
                name=row['name'],
                instructions=row['instructions'],
                is_active=row['is_active'],
                is_local_mode=row['is_local_mode'],
                initial_greeting=row['initial_greeting'],
                language=row['language'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        return None
    
    async def get_by_id(self, instruction_id: int) -> Optional[AgentInstruction]:
        """Get instruction by ID"""
        query = """
            SELECT id, name, instructions, is_active, is_local_mode,
                   initial_greeting, language, created_at, updated_at
            FROM agent_instructions
            WHERE id = $1
        """
        row = await self.pool.fetchrow(query, instruction_id)
        if row:
            return AgentInstruction(
                id=row['id'],
                name=row['name'],
                instructions=row['instructions'],
                is_active=row['is_active'],
                is_local_mode=row['is_local_mode'],
                initial_greeting=row['initial_greeting'],
                language=row['language'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        return None
    
    async def create(self, name: str, instructions: str, is_local_mode: bool = False,
                     initial_greeting: str = None, language: str = "en") -> int:
        """Create a new agent instruction"""
        query = """
            INSERT INTO agent_instructions (name, instructions, is_local_mode, initial_greeting, language)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        return await self.pool.fetchval(query, name, instructions, is_local_mode, initial_greeting, language)
    
    async def update(self, instruction_id: int, instructions: str, 
                     initial_greeting: str = None) -> bool:
        """Update an existing instruction"""
        query = """
            UPDATE agent_instructions
            SET instructions = $2, initial_greeting = $3, updated_at = NOW()
            WHERE id = $1
        """
        result = await self.pool.execute(query, instruction_id, instructions, initial_greeting)
        return result == "UPDATE 1"
    
    async def set_active(self, instruction_id: int, is_local_mode: bool) -> bool:
        """Set an instruction as active (deactivates others of same mode)"""
        async with self.pool.transaction() as conn:
            # Deactivate all of same mode
            await conn.execute(
                "UPDATE agent_instructions SET is_active = false WHERE is_local_mode = $1",
                is_local_mode
            )
            # Activate the selected one
            await conn.execute(
                "UPDATE agent_instructions SET is_active = true WHERE id = $1",
                instruction_id
            )
        return True


class SessionRepository:
    """Repository for user sessions - handles concurrent user isolation"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def create_session(
        self,
        room_id: str,
        participant_id: str,
        agent_instruction_id: int,
        llm_provider: LLMProvider,
        profile_id: str = None
    ) -> str:
        """Create a new session for a user"""
        session_id = str(uuid4())
        query = """
            INSERT INTO agent_sessions 
            (id, room_id, participant_id, agent_instruction_id, llm_provider, status, context, profile_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """
        await self.pool.execute(
            query, session_id, room_id, participant_id, 
            agent_instruction_id, llm_provider.value, SessionStatus.ACTIVE.value, '{}', profile_id
        )
        logger.info(f"Created session {session_id} for participant {participant_id} (profile: {profile_id})")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get session by ID"""
        query = """
            SELECT id, room_id, participant_id, agent_instruction_id, llm_provider,
                   status, context, message_count, created_at, last_activity, ended_at
            FROM agent_sessions
            WHERE id = $1
        """
        row = await self.pool.fetchrow(query, session_id)
        if row:
            return AgentSession(
                id=row['id'],
                room_id=row['room_id'],
                participant_id=row['participant_id'],
                agent_instruction_id=row['agent_instruction_id'],
                llm_provider=LLMProvider(row['llm_provider']),
                status=SessionStatus(row['status']),
                context=json.loads(row['context']) if row['context'] else {},
                message_count=row['message_count'],
                created_at=row['created_at'],
                last_activity=row['last_activity'],
                ended_at=row['ended_at']
            )
        return None
    
    async def get_active_session_by_room(self, room_id: str) -> Optional[AgentSession]:
        """Get active session for a room"""
        query = """
            SELECT id, room_id, participant_id, agent_instruction_id, llm_provider,
                   status, context, message_count, created_at, last_activity, ended_at
            FROM agent_sessions
            WHERE room_id = $1 AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.pool.fetchrow(query, room_id)
        if row:
            return AgentSession(
                id=row['id'],
                room_id=row['room_id'],
                participant_id=row['participant_id'],
                agent_instruction_id=row['agent_instruction_id'],
                llm_provider=LLMProvider(row['llm_provider']),
                status=SessionStatus(row['status']),
                context=json.loads(row['context']) if row['context'] else {},
                message_count=row['message_count'],
                created_at=row['created_at'],
                last_activity=row['last_activity'],
                ended_at=row['ended_at']
            )
        return None
    
    async def update_activity(self, session_id: str) -> None:
        """Update last activity timestamp"""
        query = """
            UPDATE agent_sessions
            SET last_activity = NOW(), message_count = message_count + 1
            WHERE id = $1
        """
        await self.pool.execute(query, session_id)
    
    async def update_context(self, session_id: str, context: Dict[str, Any]) -> None:
        """Update session context (for storing auth tokens, user data, etc)"""
        query = """
            UPDATE agent_sessions
            SET context = $2, last_activity = NOW()
            WHERE id = $1
        """
        await self.pool.execute(query, session_id, json.dumps(context))
    
    async def end_session(self, session_id: str, duration_seconds: int = None) -> None:
        """
        Mark session as ended and save duration
        
        Args:
            session_id: Session ID to end
            duration_seconds: Optional duration in seconds to save
        """
        if duration_seconds is not None:
            query = """
                UPDATE agent_sessions
                SET status = 'ended', ended_at = NOW(), duration_seconds = $2
                WHERE id = $1
            """
            await self.pool.execute(query, session_id, duration_seconds)
        else:
            query = """
                UPDATE agent_sessions
                SET status = 'ended', ended_at = NOW()
                WHERE id = $1
            """
            await self.pool.execute(query, session_id)
        logger.info(f"Ended session {session_id} (duration: {duration_seconds}s)")
    
    async def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        query = "SELECT COUNT(*) FROM agent_sessions WHERE status = 'active'"
        return await self.pool.fetchval(query)


class ConversationRepository:
    """Repository for conversation messages"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> int:
        """Add a message to the conversation"""
        query = """
            INSERT INTO conversation_messages (session_id, role, content, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        return await self.pool.fetchval(
            query, session_id, role, content, 
            json.dumps(metadata) if metadata else '{}'
        )
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[ConversationMessage]:
        """Get conversation history for a session"""
        query = """
            SELECT id, session_id, role, content, metadata, created_at
            FROM conversation_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
        """
        rows = await self.pool.fetch(query, session_id, limit)
        return [
            ConversationMessage(
                id=row['id'],
                session_id=row['session_id'],
                role=row['role'],
                content=row['content'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                created_at=row['created_at']
            )
            for row in rows
        ]


# NOTE: RAGDocumentRepository has been removed.
# Knowledge base queries will be handled via MCP server tools.
# The rag_documents table can be dropped or kept for migration purposes.


class ConfigRepository:
    """Repository for system configuration"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def get(self, key: str) -> Optional[str]:
        """Get a config value by key"""
        row = await self.pool.fetchrow(
            "SELECT value FROM system_config WHERE key = $1",
            key
        )
        return row['value'] if row else None
    
    async def set(self, key: str, value: str, description: str = None) -> None:
        """Set a config value"""
        query = """
            INSERT INTO system_config (key, value, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (key) DO UPDATE SET value = $2, description = $3, updated_at = NOW()
        """
        await self.pool.execute(query, key, value, description)
    
    async def get_all(self) -> Dict[str, str]:
        """Get all config values"""
        rows = await self.pool.fetch("SELECT key, value FROM system_config")
        return {row['key']: row['value'] for row in rows}


class ProfileRepository:
    """Repository for user profiles (authenticated and anonymous)"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def create_anonymous_profile(self, anonymous_id: str, metadata: Dict[str, Any] = None) -> str:
        """Create a new anonymous user profile"""
        query = """
            INSERT INTO user_profiles (profile_type, anonymous_id, profile_metadata)
            VALUES ('anonymous', $1, $2)
            RETURNING id
        """
        profile_id = await self.pool.fetchval(
            query, 
            anonymous_id, 
            json.dumps(metadata or {})
        )
        logger.info(f"Created anonymous profile: {profile_id} (anonymous_id: {anonymous_id})")
        return str(profile_id)
    
    async def create_authenticated_profile(
        self,
        username: str = None,
        phone_number: str = None,
        email: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new authenticated user profile"""
        query = """
            INSERT INTO user_profiles (
                profile_type, username, phone_number, email, 
                is_authenticated, authenticated_at, profile_metadata
            )
            VALUES ('authenticated', $1, $2, $3, true, NOW(), $4)
            RETURNING id
        """
        profile_id = await self.pool.fetchval(
            query,
            username,
            phone_number,
            email,
            json.dumps(metadata or {})
        )
        logger.info(f"Created authenticated profile: {profile_id} (username: {username})")
        return str(profile_id)
    
    async def get_by_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get profile by ID"""
        query = """
            SELECT id, profile_type, username, phone_number, email, anonymous_id,
                   profile_metadata, total_sessions, total_messages, last_seen_at,
                   is_authenticated, authenticated_at, created_at, updated_at
            FROM user_profiles
            WHERE id = $1 AND merged_into_profile_id IS NULL
        """
        row = await self.pool.fetchrow(query, profile_id)
        if row:
            return {
                'id': str(row['id']),
                'profile_type': row['profile_type'],
                'username': row['username'],
                'phone_number': row['phone_number'],
                'email': row['email'],
                'anonymous_id': row['anonymous_id'],
                'profile_metadata': json.loads(row['profile_metadata']) if row['profile_metadata'] else {},
                'total_sessions': row['total_sessions'],
                'total_messages': row['total_messages'],
                'last_seen_at': row['last_seen_at'],
                'is_authenticated': row['is_authenticated'],
                'authenticated_at': row['authenticated_at'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
    
    async def get_by_anonymous_id(self, anonymous_id: str) -> Optional[Dict[str, Any]]:
        """Get profile by anonymous ID"""
        query = """
            SELECT id, profile_type, anonymous_id, profile_metadata, 
                   total_sessions, total_messages, last_seen_at,
                   created_at, updated_at
            FROM user_profiles
            WHERE anonymous_id = $1 AND merged_into_profile_id IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.pool.fetchrow(query, anonymous_id)
        if row:
            return {
                'id': str(row['id']),
                'profile_type': row['profile_type'],
                'anonymous_id': row['anonymous_id'],
                'profile_metadata': json.loads(row['profile_metadata']) if row['profile_metadata'] else {},
                'total_sessions': row['total_sessions'],
                'total_messages': row['total_messages'],
                'last_seen_at': row['last_seen_at'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
    
    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get authenticated profile by username"""
        query = """
            SELECT id, profile_type, username, phone_number, email,
                   profile_metadata, total_sessions, total_messages, last_seen_at,
                   is_authenticated, authenticated_at, created_at, updated_at
            FROM user_profiles
            WHERE username = $1 AND merged_into_profile_id IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.pool.fetchrow(query, username)
        if row:
            return {
                'id': str(row['id']),
                'profile_type': row['profile_type'],
                'username': row['username'],
                'phone_number': row['phone_number'],
                'email': row['email'],
                'profile_metadata': json.loads(row['profile_metadata']) if row['profile_metadata'] else {},
                'total_sessions': row['total_sessions'],
                'total_messages': row['total_messages'],
                'last_seen_at': row['last_seen_at'],
                'is_authenticated': row['is_authenticated'],
                'authenticated_at': row['authenticated_at'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
    
    async def update_metadata(self, profile_id: str, metadata: Dict[str, Any]) -> bool:
        """Update profile metadata (merge with existing)"""
        query = """
            UPDATE user_profiles
            SET profile_metadata = profile_metadata || $2::jsonb,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await self.pool.execute(query, profile_id, json.dumps(metadata))
        return result == "UPDATE 1"
    
    async def merge_anonymous_to_authenticated(
        self,
        anonymous_profile_id: str,
        authenticated_profile_id: str
    ) -> bool:
        """Merge an anonymous profile into an authenticated one"""
        try:
            await self.pool.execute(
                "SELECT merge_profiles($1, $2)",
                anonymous_profile_id,
                authenticated_profile_id
            )
            logger.info(f"Merged profile {anonymous_profile_id} -> {authenticated_profile_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to merge profiles: {e}")
            return False


class ConversationSummaryRepository:
    """Repository for conversation summaries"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def create_summary(
        self,
        session_id: str,
        profile_id: str,
        summary: str,
        extracted_info: Dict[str, Any] = None,
        message_count: int = 0,
        duration_seconds: int = None,
        sentiment: str = None,
        resolution_status: str = None,
        topics: List[str] = None
    ) -> int:
        """Create a conversation summary"""
        query = """
            INSERT INTO conversation_summaries (
                session_id, profile_id, summary, extracted_info,
                message_count, duration_seconds, sentiment, 
                resolution_status, topics
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """
        summary_id = await self.pool.fetchval(
            query,
            session_id,
            profile_id,
            summary,
            json.dumps(extracted_info or {}),
            message_count,
            duration_seconds,
            sentiment,
            resolution_status,
            topics or []
        )
        logger.info(f"Created conversation summary {summary_id} for session {session_id}")
        return summary_id
    
    async def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary for a session"""
        query = """
            SELECT id, session_id, profile_id, summary, extracted_info,
                   message_count, duration_seconds, sentiment, 
                   resolution_status, topics, created_at
            FROM conversation_summaries
            WHERE session_id = $1
        """
        row = await self.pool.fetchrow(query, session_id)
        if row:
            return {
                'id': row['id'],
                'session_id': str(row['session_id']),
                'profile_id': str(row['profile_id']),
                'summary': row['summary'],
                'extracted_info': json.loads(row['extracted_info']) if row['extracted_info'] else {},
                'message_count': row['message_count'],
                'duration_seconds': row['duration_seconds'],
                'sentiment': row['sentiment'],
                'resolution_status': row['resolution_status'],
                'topics': row['topics'],
                'created_at': row['created_at']
            }
        return None
    
    async def get_by_profile(
        self,
        profile_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation summaries for a profile"""
        query = """
            SELECT id, session_id, profile_id, summary, extracted_info,
                   message_count, duration_seconds, sentiment,
                   resolution_status, topics, created_at
            FROM conversation_summaries
            WHERE profile_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        rows = await self.pool.fetch(query, profile_id, limit)
        return [
            {
                'id': row['id'],
                'session_id': str(row['session_id']),
                'profile_id': str(row['profile_id']),
                'summary': row['summary'],
                'extracted_info': json.loads(row['extracted_info']) if row['extracted_info'] else {},
                'message_count': row['message_count'],
                'duration_seconds': row['duration_seconds'],
                'sentiment': row['sentiment'],
                'resolution_status': row['resolution_status'],
                'topics': row['topics'],
                'created_at': row['created_at']
            }
            for row in rows
        ]


# ===========================================
# SHARE LINKS REPOSITORY
# ===========================================

class ShareLinkRepository:
    """Repository for shareable links"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def create(
        self,
        name: str,
        agent_instruction_id: int,
        description: str = None,
        custom_greeting: str = None,
        custom_context: Dict[str, Any] = None,
        branding: Dict[str, Any] = None,
        expires_at: datetime = None,
        max_sessions: int = None,
        allowed_domains: List[str] = None,
        require_auth: bool = False,
        created_by: str = None
    ) -> ShareLink:
        """Create a new share link"""
        link_id = str(uuid4())
        
        # Generate unique code
        code = await self.pool.fetchval("SELECT generate_share_code()")
        
        # Ensure code is unique
        while await self.get_by_code(code):
            code = await self.pool.fetchval("SELECT generate_share_code()")
        
        query = """
            INSERT INTO share_links (
                id, code, agent_instruction_id, name, description,
                custom_greeting, custom_context, branding,
                expires_at, max_sessions, allowed_domains, require_auth, created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """
        row = await self.pool.fetchrow(
            query, link_id, code, agent_instruction_id, name, description,
            custom_greeting, json.dumps(custom_context or {}), json.dumps(branding or {}),
            expires_at, max_sessions, allowed_domains, require_auth, created_by
        )
        
        logger.info(f"Created share link: {code} (id: {link_id})")
        return self._row_to_share_link(row)
    
    async def get_by_id(self, link_id: str) -> Optional[ShareLink]:
        """Get share link by ID"""
        query = "SELECT * FROM share_links WHERE id = $1"
        row = await self.pool.fetchrow(query, link_id)
        return self._row_to_share_link(row) if row else None
    
    async def get_by_code(self, code: str) -> Optional[ShareLink]:
        """Get share link by code"""
        query = "SELECT * FROM share_links WHERE code = $1"
        row = await self.pool.fetchrow(query, code)
        return self._row_to_share_link(row) if row else None
    
    async def get_all(self, include_inactive: bool = False) -> List[ShareLink]:
        """Get all share links"""
        if include_inactive:
            query = "SELECT * FROM share_links ORDER BY created_at DESC"
            rows = await self.pool.fetch(query)
        else:
            query = "SELECT * FROM share_links WHERE is_active = true ORDER BY created_at DESC"
            rows = await self.pool.fetch(query)
        return [self._row_to_share_link(row) for row in rows]
    
    async def update(
        self,
        link_id: str,
        name: str = None,
        description: str = None,
        custom_greeting: str = None,
        custom_context: Dict[str, Any] = None,
        branding: Dict[str, Any] = None,
        is_active: bool = None,
        expires_at: datetime = None,
        max_sessions: int = None,
        allowed_domains: List[str] = None
    ) -> Optional[ShareLink]:
        """Update a share link"""
        updates = []
        params = [link_id]
        param_idx = 2
        
        if name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(name)
            param_idx += 1
        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1
        if custom_greeting is not None:
            updates.append(f"custom_greeting = ${param_idx}")
            params.append(custom_greeting)
            param_idx += 1
        if custom_context is not None:
            updates.append(f"custom_context = ${param_idx}")
            params.append(json.dumps(custom_context))
            param_idx += 1
        if branding is not None:
            updates.append(f"branding = ${param_idx}")
            params.append(json.dumps(branding))
            param_idx += 1
        if is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1
        if expires_at is not None:
            updates.append(f"expires_at = ${param_idx}")
            params.append(expires_at)
            param_idx += 1
        if max_sessions is not None:
            updates.append(f"max_sessions = ${param_idx}")
            params.append(max_sessions)
            param_idx += 1
        if allowed_domains is not None:
            updates.append(f"allowed_domains = ${param_idx}")
            params.append(allowed_domains)
            param_idx += 1
        
        if not updates:
            return await self.get_by_id(link_id)
        
        query = f"""
            UPDATE share_links
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        row = await self.pool.fetchrow(query, *params)
        return self._row_to_share_link(row) if row else None
    
    async def delete(self, link_id: str) -> bool:
        """Delete a share link"""
        result = await self.pool.execute(
            "DELETE FROM share_links WHERE id = $1", link_id
        )
        return result == "DELETE 1"
    
    async def increment_stats(self, link_id: str, messages: int = 0) -> None:
        """Increment share link statistics"""
        await self.pool.execute(
            "SELECT increment_share_link_stats($1, $2)", link_id, messages
        )
    
    async def record_analytics(
        self,
        share_link_id: str,
        event_type: str,
        session_id: str = None,
        visitor_ip: str = None,
        user_agent: str = None,
        referrer: str = None,
        country: str = None,
        city: str = None,
        messages_count: int = 0,
        duration_seconds: int = None,
        event_data: Dict[str, Any] = None
    ) -> int:
        """Record an analytics event"""
        query = """
            INSERT INTO share_link_analytics (
                share_link_id, session_id, event_type,
                visitor_ip, user_agent, referrer, country, city,
                messages_count, duration_seconds, event_data
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """
        return await self.pool.fetchval(
            query, share_link_id, session_id, event_type,
            visitor_ip, user_agent, referrer, country, city,
            messages_count, duration_seconds, json.dumps(event_data or {})
        )
    
    async def get_analytics(
        self,
        share_link_id: str,
        limit: int = 100,
        event_type: str = None
    ) -> List[Dict[str, Any]]:
        """Get analytics for a share link"""
        if event_type:
            query = """
                SELECT * FROM share_link_analytics
                WHERE share_link_id = $1 AND event_type = $3
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await self.pool.fetch(query, share_link_id, limit, event_type)
        else:
            query = """
                SELECT * FROM share_link_analytics
                WHERE share_link_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await self.pool.fetch(query, share_link_id, limit)
        
        return [
            {
                'id': row['id'],
                'share_link_id': str(row['share_link_id']),
                'session_id': str(row['session_id']) if row['session_id'] else None,
                'event_type': row['event_type'],
                'visitor_ip': row['visitor_ip'],
                'user_agent': row['user_agent'],
                'referrer': row['referrer'],
                'country': row['country'],
                'city': row['city'],
                'messages_count': row['messages_count'],
                'duration_seconds': row['duration_seconds'],
                'event_data': json.loads(row['event_data']) if row['event_data'] else {},
                'created_at': row['created_at']
            }
            for row in rows
        ]
    
    def _row_to_share_link(self, row) -> ShareLink:
        """Convert database row to ShareLink model"""
        branding_data = json.loads(row['branding']) if row['branding'] else {}
        return ShareLink(
            id=str(row['id']),
            code=row['code'],
            agent_instruction_id=row['agent_instruction_id'],
            name=row['name'],
            description=row['description'],
            custom_greeting=row['custom_greeting'],
            custom_context=json.loads(row['custom_context']) if row['custom_context'] else {},
            branding=ShareLinkBranding.from_dict(branding_data),
            is_active=row['is_active'],
            expires_at=row['expires_at'],
            max_sessions=row['max_sessions'],
            allowed_domains=row['allowed_domains'],
            require_auth=row['require_auth'],
            total_sessions=row['total_sessions'],
            total_messages=row['total_messages'],
            last_used_at=row['last_used_at'],
            created_by=row['created_by'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


# ===========================================
# EMBED API KEYS REPOSITORY
# ===========================================

class EmbedApiKeyRepository:
    """Repository for embed API keys"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    def _generate_api_key(self) -> tuple[str, str, str]:
        """Generate a new API key. Returns (full_key, key_hash, key_prefix)"""
        # Generate a secure random key
        full_key = f"tncb_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        key_prefix = full_key[:12]
        return full_key, key_hash, key_prefix
    
    async def create(
        self,
        name: str,
        allowed_domains: List[str],
        agent_instruction_id: int = None,
        description: str = None,
        custom_greeting: str = None,
        custom_context: Dict[str, Any] = None,
        branding: Dict[str, Any] = None,
        widget_config: Dict[str, Any] = None,
        rate_limit_rpm: int = 60,
        max_concurrent_sessions: int = 10,
        created_by: str = None
    ) -> tuple[EmbedApiKey, str]:
        """Create a new embed API key. Returns (EmbedApiKey, full_key)"""
        key_id = str(uuid4())
        full_key, key_hash, key_prefix = self._generate_api_key()
        
        query = """
            INSERT INTO embed_api_keys (
                id, key_hash, key_prefix, name, description, agent_instruction_id,
                custom_greeting, custom_context, branding, widget_config,
                allowed_domains, rate_limit_rpm, max_concurrent_sessions, created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING *
        """
        row = await self.pool.fetchrow(
            query, key_id, key_hash, key_prefix, name, description, agent_instruction_id,
            custom_greeting, json.dumps(custom_context or {}), json.dumps(branding or {}),
            json.dumps(widget_config or {}), allowed_domains, rate_limit_rpm,
            max_concurrent_sessions, created_by
        )
        
        logger.info(f"Created embed API key: {key_prefix}... (id: {key_id})")
        return self._row_to_embed_key(row), full_key
    
    async def get_by_id(self, key_id: str) -> Optional[EmbedApiKey]:
        """Get embed key by ID"""
        query = "SELECT * FROM embed_api_keys WHERE id = $1"
        row = await self.pool.fetchrow(query, key_id)
        return self._row_to_embed_key(row) if row else None
    
    async def get_by_key(self, api_key: str) -> Optional[EmbedApiKey]:
        """Get embed key by full API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        query = "SELECT * FROM embed_api_keys WHERE key_hash = $1"
        row = await self.pool.fetchrow(query, key_hash)
        return self._row_to_embed_key(row) if row else None
    
    async def get_all(self, include_inactive: bool = False) -> List[EmbedApiKey]:
        """Get all embed API keys"""
        if include_inactive:
            query = "SELECT * FROM embed_api_keys ORDER BY created_at DESC"
            rows = await self.pool.fetch(query)
        else:
            query = "SELECT * FROM embed_api_keys WHERE is_active = true ORDER BY created_at DESC"
            rows = await self.pool.fetch(query)
        return [self._row_to_embed_key(row) for row in rows]
    
    async def update(
        self,
        key_id: str,
        name: str = None,
        description: str = None,
        agent_instruction_id: int = None,
        custom_greeting: str = None,
        custom_context: Dict[str, Any] = None,
        branding: Dict[str, Any] = None,
        widget_config: Dict[str, Any] = None,
        is_active: bool = None,
        allowed_domains: List[str] = None,
        rate_limit_rpm: int = None,
        max_concurrent_sessions: int = None
    ) -> Optional[EmbedApiKey]:
        """Update an embed API key"""
        updates = []
        params = [key_id]
        param_idx = 2
        
        if name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(name)
            param_idx += 1
        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1
        if agent_instruction_id is not None:
            updates.append(f"agent_instruction_id = ${param_idx}")
            params.append(agent_instruction_id)
            param_idx += 1
        if custom_greeting is not None:
            updates.append(f"custom_greeting = ${param_idx}")
            params.append(custom_greeting)
            param_idx += 1
        if custom_context is not None:
            updates.append(f"custom_context = ${param_idx}")
            params.append(json.dumps(custom_context))
            param_idx += 1
        if branding is not None:
            updates.append(f"branding = ${param_idx}")
            params.append(json.dumps(branding))
            param_idx += 1
        if widget_config is not None:
            updates.append(f"widget_config = ${param_idx}")
            params.append(json.dumps(widget_config))
            param_idx += 1
        if is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1
        if allowed_domains is not None:
            updates.append(f"allowed_domains = ${param_idx}")
            params.append(allowed_domains)
            param_idx += 1
        if rate_limit_rpm is not None:
            updates.append(f"rate_limit_rpm = ${param_idx}")
            params.append(rate_limit_rpm)
            param_idx += 1
        if max_concurrent_sessions is not None:
            updates.append(f"max_concurrent_sessions = ${param_idx}")
            params.append(max_concurrent_sessions)
            param_idx += 1
        
        if not updates:
            return await self.get_by_id(key_id)
        
        query = f"""
            UPDATE embed_api_keys
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        row = await self.pool.fetchrow(query, *params)
        return self._row_to_embed_key(row) if row else None
    
    async def delete(self, key_id: str) -> bool:
        """Delete an embed API key"""
        result = await self.pool.execute(
            "DELETE FROM embed_api_keys WHERE id = $1", key_id
        )
        return result == "DELETE 1"
    
    async def regenerate_key(self, key_id: str) -> Optional[tuple[EmbedApiKey, str]]:
        """Regenerate the API key. Returns (EmbedApiKey, new_full_key)"""
        full_key, key_hash, key_prefix = self._generate_api_key()
        
        query = """
            UPDATE embed_api_keys
            SET key_hash = $2, key_prefix = $3, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        row = await self.pool.fetchrow(query, key_id, key_hash, key_prefix)
        if row:
            logger.info(f"Regenerated embed API key: {key_prefix}... (id: {key_id})")
            return self._row_to_embed_key(row), full_key
        return None
    
    async def increment_stats(self, key_id: str, messages: int = 0) -> None:
        """Increment embed key statistics"""
        await self.pool.execute(
            "SELECT increment_embed_key_stats($1, $2)", key_id, messages
        )
    
    async def validate_domain(self, key_id: str, domain: str) -> bool:
        """Check if a domain is allowed for this key"""
        key = await self.get_by_id(key_id)
        if not key or not key.is_active:
            return False
        
        # Check if domain matches any allowed pattern
        for allowed in key.allowed_domains:
            if allowed == '*':
                return True
            if allowed.startswith('*.'):
                # Wildcard subdomain match
                pattern = allowed[2:]
                if domain == pattern or domain.endswith('.' + pattern):
                    return True
            elif domain == allowed:
                return True
        
        return False
    
    def _row_to_embed_key(self, row) -> EmbedApiKey:
        """Convert database row to EmbedApiKey model"""
        branding_data = json.loads(row['branding']) if row['branding'] else {}
        widget_data = json.loads(row['widget_config']) if row['widget_config'] else {}
        return EmbedApiKey(
            id=str(row['id']),
            key_hash=row['key_hash'],
            key_prefix=row['key_prefix'],
            name=row['name'],
            description=row['description'],
            agent_instruction_id=row['agent_instruction_id'],
            custom_greeting=row['custom_greeting'],
            custom_context=json.loads(row['custom_context']) if row['custom_context'] else {},
            branding=ShareLinkBranding.from_dict(branding_data),
            widget_config=WidgetConfig.from_dict(widget_data),
            is_active=row['is_active'],
            allowed_domains=row['allowed_domains'] or [],
            rate_limit_rpm=row['rate_limit_rpm'],
            max_concurrent_sessions=row['max_concurrent_sessions'],
            total_sessions=row['total_sessions'],
            total_messages=row['total_messages'],
            last_used_at=row['last_used_at'],
            created_by=row['created_by'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


# ===========================================
# EMBED SESSIONS REPOSITORY
# ===========================================

class EmbedSessionRepository:
    """Repository for embed sessions"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
    async def create(
        self,
        embed_key_id: str,
        origin_domain: str,
        visitor_id: str = None,
        session_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> EmbedSession:
        """Create a new embed session"""
        embed_session_id = str(uuid4())
        
        query = """
            INSERT INTO embed_sessions (
                id, embed_key_id, session_id, origin_domain, visitor_id, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """
        row = await self.pool.fetchrow(
            query, embed_session_id, embed_key_id, session_id,
            origin_domain, visitor_id, json.dumps(metadata or {})
        )
        
        logger.info(f"Created embed session: {embed_session_id} for key {embed_key_id}")
        return self._row_to_embed_session(row)
    
    async def get_by_id(self, embed_session_id: str) -> Optional[EmbedSession]:
        """Get embed session by ID"""
        query = "SELECT * FROM embed_sessions WHERE id = $1"
        row = await self.pool.fetchrow(query, embed_session_id)
        return self._row_to_embed_session(row) if row else None
    
    async def link_agent_session(self, embed_session_id: str, session_id: str) -> bool:
        """Link an agent session to this embed session"""
        result = await self.pool.execute(
            "UPDATE embed_sessions SET session_id = $2 WHERE id = $1",
            embed_session_id, session_id
        )
        return result == "UPDATE 1"
    
    async def update_stats(
        self,
        embed_session_id: str,
        messages_count: int = None,
        duration_seconds: int = None
    ) -> None:
        """Update session statistics"""
        updates = []
        params = [embed_session_id]
        param_idx = 2
        
        if messages_count is not None:
            updates.append(f"messages_count = ${param_idx}")
            params.append(messages_count)
            param_idx += 1
        if duration_seconds is not None:
            updates.append(f"duration_seconds = ${param_idx}")
            params.append(duration_seconds)
            param_idx += 1
        
        if updates:
            query = f"UPDATE embed_sessions SET {', '.join(updates)} WHERE id = $1"
            await self.pool.execute(query, *params)
    
    async def end_session(self, embed_session_id: str, duration_seconds: int = None) -> None:
        """Mark embed session as ended"""
        if duration_seconds is not None:
            await self.pool.execute(
                "UPDATE embed_sessions SET status = 'ended', ended_at = NOW(), duration_seconds = $2 WHERE id = $1",
                embed_session_id, duration_seconds
            )
        else:
            await self.pool.execute(
                "UPDATE embed_sessions SET status = 'ended', ended_at = NOW() WHERE id = $1",
                embed_session_id
            )
    
    async def get_active_count_for_key(self, embed_key_id: str) -> int:
        """Get count of active sessions for an embed key"""
        return await self.pool.fetchval(
            "SELECT COUNT(*) FROM embed_sessions WHERE embed_key_id = $1 AND status = 'active'",
            embed_key_id
        )
    
    def _row_to_embed_session(self, row) -> EmbedSession:
        """Convert database row to EmbedSession model"""
        return EmbedSession(
            id=str(row['id']),
            embed_key_id=str(row['embed_key_id']),
            session_id=str(row['session_id']) if row['session_id'] else None,
            origin_domain=row['origin_domain'],
            visitor_id=row['visitor_id'],
            messages_count=row['messages_count'],
            duration_seconds=row['duration_seconds'],
            status=EmbedSessionStatus(row['status']),
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            created_at=row['created_at'],
            ended_at=row['ended_at']
        )
