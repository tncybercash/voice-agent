"""
Database models for the AI Voice Agent system.
Supports PostgreSQL for session and conversation storage.

Note: RAG-related models (RAGDocument) have been deprecated.
Knowledge base queries will be handled via MCP server tools.
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENROUTER = "openrouter"
    GOOGLE = "google"
    GOOGLE_REALTIME = "google_realtime"


class SessionStatus(str, Enum):
    """Session lifecycle states"""
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class AgentInstruction:
    """Agent instruction configuration stored in database"""
    id: int
    name: str
    instructions: str
    is_active: bool = True
    is_local_mode: bool = False
    initial_greeting: Optional[str] = None
    language: str = "en"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentSession:
    """User session for conversation isolation"""
    id: str  # UUID
    room_id: str
    participant_id: str
    agent_instruction_id: int
    llm_provider: LLMProvider
    status: SessionStatus = SessionStatus.ACTIVE
    context: dict = field(default_factory=dict)  # Session-specific context
    message_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


@dataclass
class ConversationMessage:
    """Individual message in a conversation"""
    id: int
    session_id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


# NOTE: RAGDocument model has been deprecated.
# Knowledge base queries will be handled via MCP server tools.
# This model is kept for backward compatibility but should not be used.
# The rag_documents table can be dropped from the database.


@dataclass
class SystemConfig:
    """System-wide configuration stored in database"""
    id: int
    key: str
    value: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
