"""Database package initialization

Note: RAG-related functionality has been removed from this module.
Knowledge base queries will be handled via MCP server tools.
The RAGDocument model is kept for backward compatibility but is deprecated.
"""
from .models import (
    AgentInstruction,
    AgentSession,
    ConversationMessage,
    SystemConfig,
    LLMProvider,
    SessionStatus
)
from .connection import DatabasePool, get_db_pool
from .repository import (
    ProfileRepository,
    ConversationSummaryRepository
)

__all__ = [
    "AgentInstruction",
    "AgentSession",
    "ConversationMessage",
    "SystemConfig",
    "LLMProvider",
    "SessionStatus",
    "DatabasePool",
    "get_db_pool",
    "ProfileRepository",
    "ConversationSummaryRepository"
]
