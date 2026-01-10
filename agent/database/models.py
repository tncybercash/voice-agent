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


# ===========================================
# SHARE LINKS MODELS
# ===========================================

@dataclass
class ShareLinkBranding:
    """Branding configuration for share links"""
    logo_url: Optional[str] = None
    accent_color: Optional[str] = None
    company_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'logo_url': self.logo_url,
            'accent_color': self.accent_color,
            'company_name': self.company_name
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ShareLinkBranding':
        return cls(
            logo_url=data.get('logo_url'),
            accent_color=data.get('accent_color'),
            company_name=data.get('company_name')
        )


@dataclass
class ShareLink:
    """Shareable link for agent access"""
    id: str  # UUID
    code: str
    agent_instruction_id: int
    name: str
    description: Optional[str] = None
    
    # Customization
    custom_greeting: Optional[str] = None
    custom_context: dict = field(default_factory=dict)
    branding: ShareLinkBranding = field(default_factory=ShareLinkBranding)
    
    # Access Control
    is_active: bool = True
    expires_at: Optional[datetime] = None
    max_sessions: Optional[int] = None
    allowed_domains: Optional[List[str]] = None
    require_auth: bool = False
    
    # Stats
    total_sessions: int = 0
    total_messages: int = 0
    last_used_at: Optional[datetime] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_valid(self) -> bool:
        """Check if share link is valid for use"""
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        if self.max_sessions and self.total_sessions >= self.max_sessions:
            return False
        return True


@dataclass
class ShareLinkAnalytics:
    """Analytics event for share link usage"""
    id: int
    share_link_id: str  # UUID
    session_id: Optional[str] = None  # UUID
    
    # Request Info
    visitor_ip: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    
    # Session Info
    messages_count: int = 0
    duration_seconds: Optional[int] = None
    
    # Event
    event_type: str = 'session_start'
    event_data: dict = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)


# ===========================================
# EMBED SYSTEM MODELS
# ===========================================

@dataclass
class WidgetConfig:
    """Widget display configuration"""
    position: str = 'bottom-right'  # bottom-right, bottom-left, top-right, top-left
    theme: str = 'auto'  # auto, light, dark
    size: str = 'medium'  # small, medium, large
    button_text: str = 'Chat with us'
    button_icon: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'position': self.position,
            'theme': self.theme,
            'size': self.size,
            'button_text': self.button_text,
            'button_icon': self.button_icon
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'WidgetConfig':
        return cls(
            position=data.get('position', 'bottom-right'),
            theme=data.get('theme', 'auto'),
            size=data.get('size', 'medium'),
            button_text=data.get('button_text', 'Chat with us'),
            button_icon=data.get('button_icon')
        )


@dataclass
class EmbedApiKey:
    """API key for embedding the agent"""
    id: str  # UUID
    key_hash: str  # SHA-256 hash
    key_prefix: str  # First 8 chars
    name: str
    description: Optional[str] = None
    
    # Linked Agent
    agent_instruction_id: int = None
    
    # Customization
    custom_greeting: Optional[str] = None
    custom_context: dict = field(default_factory=dict)
    branding: ShareLinkBranding = field(default_factory=ShareLinkBranding)
    widget_config: WidgetConfig = field(default_factory=WidgetConfig)
    
    # Access Control
    is_active: bool = True
    allowed_domains: List[str] = field(default_factory=list)
    rate_limit_rpm: int = 60
    max_concurrent_sessions: int = 10
    
    # Stats
    total_sessions: int = 0
    total_messages: int = 0
    last_used_at: Optional[datetime] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class EmbedSessionStatus(str, Enum):
    """Embed session states"""
    ACTIVE = "active"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class EmbedSession:
    """Session created through embed widget"""
    id: str  # UUID
    embed_key_id: str  # UUID
    session_id: Optional[str] = None  # UUID - linked agent session
    
    # Origin Info
    origin_domain: str = ""
    visitor_id: Optional[str] = None
    
    # Session Info
    messages_count: int = 0
    duration_seconds: Optional[int] = None
    status: EmbedSessionStatus = EmbedSessionStatus.ACTIVE
    
    # Metadata
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
