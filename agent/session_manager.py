"""
Session Manager for concurrent user handling.
Ensures each user has isolated conversation context with no overlap.
"""
import os
import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4

from database import (
    get_db_pool,
    LLMProvider as LLMProviderEnum,
    SessionStatus
)
from database.repository import (
    AgentInstructionRepository,
    SessionRepository,
    ConversationRepository,
    ConfigRepository
)
from providers import get_llm_provider_manager, LLMProviderType

logger = logging.getLogger("session_manager")


@dataclass
class UserSession:
    """
    Represents an active user session with isolated context.
    Each user gets their own session for concurrent conversations.
    """
    session_id: str
    room_id: str
    participant_id: str
    instructions: str
    initial_greeting: Optional[str]
    llm_provider: LLMProviderType
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    
    # Session-specific data (auth tokens, user data, etc)
    auth_token: Optional[str] = None
    user_data: Dict[str, Any] = field(default_factory=dict)
    conversation_history: list = field(default_factory=list)


class SessionManager:
    """
    Manages concurrent user sessions with database persistence.
    Supports 20+ simultaneous users with isolated conversations.
    """
    
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._room_to_session: Dict[str, str] = {}  # room_id -> session_id
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._db_pool = None
        self._llm_manager = None
    
    async def initialize(self) -> None:
        """Initialize the session manager"""
        self._db_pool = await get_db_pool()
        self._llm_manager = await get_llm_provider_manager()
        
        # Start cleanup task for stale sessions
        self._cleanup_task = asyncio.create_task(self._cleanup_stale_sessions())
        
        logger.info("Session manager initialized")
    
    async def create_session(
        self,
        room_id: str,
        participant_id: str,
        llm_provider: LLMProviderType = None,
        is_local_mode: bool = True
    ) -> UserSession:
        """
        Create a new session for a user.
        Each room gets exactly one active session.
        """
        async with self._lock:
            # Check if room already has an active session
            if room_id in self._room_to_session:
                existing_id = self._room_to_session[room_id]
                if existing_id in self._sessions:
                    logger.info(f"Returning existing session for room {room_id}")
                    return self._sessions[existing_id]
            
            # Get instructions from database
            instruction_repo = AgentInstructionRepository(self._db_pool)
            instruction = await instruction_repo.get_active_instruction(is_local_mode)
            
            if not instruction:
                # Fallback to default instructions
                from prompt import AGENT_INSTRUCTIONS, AGENT_INSTRUCTIONS_LOCAL
                instructions = AGENT_INSTRUCTIONS_LOCAL if is_local_mode else AGENT_INSTRUCTIONS
                initial_greeting = None
                instruction_id = 0
            else:
                instructions = instruction.instructions
                initial_greeting = instruction.initial_greeting
                instruction_id = instruction.id
            
            # Determine LLM provider
            if llm_provider is None:
                provider_env = os.getenv("LLM_PROVIDER", "ollama").lower()
                if provider_env == "vllm":
                    llm_provider = LLMProviderType.VLLM
                elif provider_env == "openrouter":
                    llm_provider = LLMProviderType.OPENROUTER
                else:
                    llm_provider = LLMProviderType.OLLAMA
            
            # Create session in database
            session_repo = SessionRepository(self._db_pool)
            session_id = await session_repo.create_session(
                room_id=room_id,
                participant_id=participant_id,
                agent_instruction_id=instruction_id,
                llm_provider=LLMProviderEnum(llm_provider.value)
            )
            
            # Create in-memory session
            session = UserSession(
                session_id=session_id,
                room_id=room_id,
                participant_id=participant_id,
                instructions=instructions,
                initial_greeting=initial_greeting,
                llm_provider=llm_provider
            )
            
            self._sessions[session_id] = session
            self._room_to_session[room_id] = session_id
            
            logger.info(f"Created session {session_id} for room {room_id}, provider: {llm_provider.value}")
            return session
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID"""
        return self._sessions.get(session_id)
    
    async def get_session_by_room(self, room_id: str) -> Optional[UserSession]:
        """Get session for a room"""
        session_id = self._room_to_session.get(room_id)
        if session_id:
            return self._sessions.get(session_id)
        return None
    
    async def update_session_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Update session context (auth tokens, user data, etc)"""
        session = self._sessions.get(session_id)
        if session:
            session.context.update(context)
            session.last_activity = datetime.utcnow()
            
            # Persist to database
            session_repo = SessionRepository(self._db_pool)
            await session_repo.update_context(session_id, session.context)
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a message to the session's conversation history"""
        session = self._sessions.get(session_id)
        if session:
            session.conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            })
            session.message_count += 1
            session.last_activity = datetime.utcnow()
            
            # Persist to database
            conv_repo = ConversationRepository(self._db_pool)
            await conv_repo.add_message(session_id, role, content, metadata)
            
            # Update session activity
            session_repo = SessionRepository(self._db_pool)
            await session_repo.update_activity(session_id)
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> list:
        """Get recent conversation history for a session"""
        session = self._sessions.get(session_id)
        if session:
            return session.conversation_history[-limit:]
        return []
    
    async def end_session(self, session_id: str) -> None:
        """End a session and cleanup"""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                # Remove room mapping
                if session.room_id in self._room_to_session:
                    del self._room_to_session[session.room_id]
                
                # Mark as ended in database
                session_repo = SessionRepository(self._db_pool)
                await session_repo.end_session(session_id)
                
                logger.info(f"Ended session {session_id}")
    
    async def end_session_by_room(self, room_id: str) -> None:
        """End session for a room"""
        session_id = self._room_to_session.get(room_id)
        if session_id:
            await self.end_session(session_id)
    
    async def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        return len(self._sessions)
    
    async def get_all_active_sessions(self) -> Dict[str, UserSession]:
        """Get all active sessions"""
        return dict(self._sessions)
    
    async def _cleanup_stale_sessions(self) -> None:
        """Periodically cleanup stale sessions"""
        timeout_minutes = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.utcnow()
                timeout = timedelta(minutes=timeout_minutes)
                
                stale_sessions = []
                for session_id, session in self._sessions.items():
                    if now - session.last_activity > timeout:
                        stale_sessions.append(session_id)
                
                for session_id in stale_sessions:
                    logger.info(f"Cleaning up stale session: {session_id}")
                    await self.end_session(session_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
    
    async def close(self) -> None:
        """Shutdown the session manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # End all active sessions
        for session_id in list(self._sessions.keys()):
            await self.end_session(session_id)
        
        logger.info("Session manager closed")


# Singleton instance
_session_manager: Optional[SessionManager] = None
_manager_lock = asyncio.Lock()


async def get_session_manager() -> SessionManager:
    """Get or create the global session manager"""
    global _session_manager
    
    async with _manager_lock:
        if _session_manager is None:
            _session_manager = SessionManager()
            await _session_manager.initialize()
        return _session_manager
