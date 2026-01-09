"""
Repository layer for database operations.
Provides async CRUD operations for all models.

Note: RAG-related repositories have been removed. Knowledge base queries
will be handled via MCP server tools.
"""
import json
import logging
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
    SessionStatus
)

logger = logging.getLogger("repository")


class AgentInstructionRepository:
    """Repository for agent instructions"""
    
    def __init__(self, pool: DatabasePool):
        self.pool = pool
    
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
