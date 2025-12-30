"""
Enhanced Voice AI Agent with database-backed configuration,
concurrent session management, and RAG support.
Optimized for 20+ concurrent users with isolated conversations.
"""
import logging
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession, room_io
from livekit.plugins import openai, silero

# Try to import Google plugin (optional)
try:
    from livekit.plugins import google
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    google = None

load_dotenv()

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.INFO)

# Import our custom modules
from session_manager import get_session_manager, UserSession
from providers import get_llm_provider_manager, LLMProviderType
from database import get_db_pool
from database.rag import RAGIndexer, RAGService, EmbeddingService

# Explicitly import tools to pass to AgentSession
from tools import (
    send_email,
    search_web
)

# Create tools list for AgentSession
AGENT_TOOLS = [
    send_email,
    search_web
]


def is_banking_question(text: str) -> bool:
    """
    Detect if a user's question is banking-related and requires RAG knowledge base.
    Returns True only for banking-specific queries.
    Uses fuzzy matching for common variations and misspellings.
    """
    text_lower = text.lower()
    # Remove punctuation and extra spaces for better matching
    text_normalized = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text_lower)
    text_normalized = ' '.join(text_normalized.split())
    
    # Banking-related keywords with common variations
    banking_keywords = [
        # Account operations
        'balance', 'account', 'transfer', 'deposit', 'withdraw', 'cardless',
        'statement', 'transaction', 'money', 'payment', 'send money',
        
        # USSD and codes (all variations)
        'ussd', 'uss d', 'us sd', 'u s s d', 'decode', 'de code',
        '*236', '*236#', 'star 236', 'dial', 'code',
        'short code', 'banking code', 'mobile code',
        
        # Digital banking channels
        'digital', 'online', 'mobile', 'app', 'website', 'portal',
        'internet banking', 'e-banking', 'channel', 'platform',
        
        # Banking services
        'loan', 'interest', 'fee', 'charge', 'branch', 'atm',
        'card', 'debit', 'credit', 'visa', 'mastercard',
        'pin', 'password', 'otp', 'verification',
        
        # Account management
        'open account', 'close account', 'new account', 'register',
        'activate', 'deactivate', 'suspend', 'freeze',
        
        # Financial products
        'limit', 'overdraft', 'savings', 'checking', 'current',
        'fixed deposit', 'foreign exchange', 'forex', 'rate',
        
        # Service
        'hours', 'contact', 'customer service', 'office', 'support',
        'help', 'assistance', 'bank', 'banking'
    ]
    
    # Check if any banking keyword is in the question
    for keyword in banking_keywords:
        if keyword in text_normalized:
            logger.info(f"🏦 Banking question detected (keyword: '{keyword}'): {text[:50]}...")
            return True
    
    # Additional pattern matching for codes
    if '*' in text or 'star' in text_lower:
        logger.info(f"🏦 Banking question detected (code pattern): {text[:50]}...")
        return True
    
    logger.info(f"💬 General question detected (no RAG needed): {text[:50]}...")
    return False


# Global references for pre-initialized services
_rag_service: RAGService = None
_db_initialized: bool = False
_initialization_lock = None  # Will be created per event loop


async def ensure_services_initialized():
    """
    Ensure database and RAG services are initialized (once per worker process).
    This runs in the worker's event loop, avoiding event loop conflicts.
    """
    global _rag_service, _db_initialized, _initialization_lock
    
    # Create lock if needed (per event loop)
    if _initialization_lock is None:
        _initialization_lock = asyncio.Lock()
    
    async with _initialization_lock:
        # Skip if already initialized in this process
        if _db_initialized and _rag_service is not None:
            return
        
        logger.info("=" * 50)
        logger.info("Initializing agent services...")
        logger.info("=" * 50)
        
        # 1. Initialize database connection
        try:
            await get_db_pool()
            _db_initialized = True
            logger.info("✓ Database connection established")
        except Exception as e:
            logger.error(f"✗ Database initialization failed: {e}")
        
        # 2. Initialize RAG service and index documents
        if os.getenv("RAG_ENABLED", "true").lower() == "true":
            try:
                _rag_service = await setup_rag_service()
                if _rag_service:
                    logger.info("✓ RAG service ready with indexed documents")
                else:
                    logger.warning("✗ RAG service not available")
            except Exception as e:
                logger.error(f"✗ RAG initialization failed: {e}")
        
        logger.info("=" * 50)
        logger.info("Services initialized!")
        logger.info("=" * 50)


class VoiceAgent(Agent):
    """
    Voice AI Agent with database-backed instructions and RAG support.
    Each instance gets isolated session context.
    """
    
    def __init__(self, session: UserSession) -> None:
        super().__init__(instructions=session.instructions)
        self.user_session = session
        self.rag_service = None
        self.base_instructions = session.instructions
        self._last_user_message = None
    
    def set_rag_service(self, rag_service: RAGService):
        """Set RAG service for context augmentation"""
        self.rag_service = rag_service
    
    async def _augment_chat_context(self, turn_ctx, user_message: str) -> str:
        """
        Augment the chat context with RAG context based on user message.
        
        IMPORTANT: We modify turn_ctx directly because that's what LiveKit uses
        for the LLM generation. Just calling update_instructions() is NOT enough!
        
        Returns:
            str: The RAG context that was added (empty string if no context found)
        """
        rag_context = ""
        
        if self.rag_service:
            try:
                logger.info(f"🔍 Searching RAG for query: '{user_message}'")
                augmented = await self.rag_service.augment_prompt(
                    user_query=user_message,
                    base_instructions=self.base_instructions
                )
                
                # Extract just the RAG context (remove base instructions)
                if len(augmented) > len(self.base_instructions):
                    rag_context = augmented[len(self.base_instructions):]
                    context_added = len(rag_context)
                    logger.info(f"✓ RAG context added ({context_added} chars) for: {user_message[:50]}...")
                    
                    # Log if USSD code is in context (for debugging)
                    if "*236#" in augmented:
                        logger.info("✓ USSD code *236# found in augmented instructions!")
                    else:
                        logger.warning("⚠ USSD code *236# NOT found in augmented instructions")
                    
                    # CRITICAL: Update the chat context's system message directly!
                    # This is what the LLM actually sees
                    if turn_ctx.items:
                        # Find and update the system message
                        for i, item in enumerate(turn_ctx.items):
                            if hasattr(item, 'role') and item.role == 'system':
                                # Create new system message with augmented instructions
                                # Note: content must be a list for ChatMessage
                                from livekit.agents import llm as llm_mod
                                new_system_msg = llm_mod.ChatMessage(
                                    id=item.id,
                                    role='system',
                                    content=[augmented]  # Must be a list!
                                )
                                turn_ctx.items[i] = new_system_msg
                                logger.info("✓ Updated system message in chat context with RAG")
                                break
                        else:
                            # No system message found, prepend one
                            from livekit.agents import llm as llm_mod
                            new_system_msg = llm_mod.ChatMessage(
                                id='rag_system',
                                role='system', 
                                content=[augmented]  # Must be a list!
                            )
                            turn_ctx.items.insert(0, new_system_msg)
                            logger.info("✓ Added new system message to chat context with RAG")
                else:
                    logger.info(f"⚠ No relevant RAG context found for: {user_message[:50]}...")
                    
            except Exception as e:
                logger.warning(f"Failed to augment with RAG: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning("RAG service not available for augmentation")
        
        return rag_context
    
    async def on_user_turn_completed(
        self, turn_ctx, new_message
    ) -> None:
        """
        Override: Called when user has finished speaking, BEFORE the LLM responds.
        This is the perfect hook for RAG augmentation.
        
        IMPORTANT: We modify turn_ctx directly (which is a mutable copy of chat_ctx)
        because that's what gets passed to _generate_reply. Just calling
        update_instructions() alone doesn't work!
        
        Args:
            turn_ctx: The mutable chat context for this turn (MODIFY THIS!)
            new_message: The new user message
        """
        # Get the user's message text
        user_text = ""
        if hasattr(new_message, 'content'):
            if isinstance(new_message.content, str):
                user_text = new_message.content
            elif isinstance(new_message.content, list):
                # Handle list of content items
                for item in new_message.content:
                    if hasattr(item, 'text'):
                        user_text += item.text
                    elif isinstance(item, str):
                        user_text += item
        else:
            user_text = str(new_message)
        
        logger.info(f"👤 User turn completed: '{user_text}'")
        self._last_user_message = user_text
        
        # Check if user is giving permission to search web
        user_lower = user_text.lower()
        if hasattr(self.user_session, 'waiting_for_search_permission'):
            if self.user_session.waiting_for_search_permission:
                if any(word in user_lower for word in ['yes', 'yeah', 'sure', 'okay', 'ok', 'go ahead', 'please']):
                    self.user_session.web_search_approved = True
                    self.user_session.waiting_for_search_permission = False
                    logger.info("✅ User approved web search")
                    
                    # Add instruction to USE the search_web tool now
                    search_instruction = f"\n\nIMPORTANT: The user has approved web search. You MUST now call the search_web tool with the query: '{getattr(self.user_session, 'pending_search_query', user_text)}'. Do not ask again, just use the tool immediately."
                    if hasattr(turn_ctx, 'items') and len(turn_ctx.items) > 0:
                        for i, item in enumerate(turn_ctx.items):
                            if hasattr(item, 'role') and item.role == 'system':
                                from livekit.agents import llm as llm_mod
                                current_content = item.content[0] if isinstance(item.content, list) else item.content
                                new_system_msg = llm_mod.ChatMessage(
                                    id=item.id,
                                    role='system',
                                    content=[current_content + search_instruction]
                                )
                                turn_ctx.items[i] = new_system_msg
                                logger.info("✓ Added search_web execution instruction to system message")
                                break
                    return  # Don't do RAG search, let tool execute
                    
                elif any(word in user_lower for word in ['no', 'nope', 'don\'t', 'not']):
                    self.user_session.web_search_approved = False
                    self.user_session.waiting_for_search_permission = False
                    logger.info("❌ User declined web search")
        
        # Determine if this is a banking question
        is_banking = is_banking_question(user_text)
        
        if is_banking:
            # Banking question - use RAG first, then ask permission if no info found
            logger.info(f"🏦 Banking question detected: {user_text[:50]}...")
            rag_context = await self._augment_chat_context(turn_ctx, user_text)
            
            # If RAG found nothing, ask permission to search web
            if not rag_context or len(rag_context.strip()) == 0:
                logger.info("⚠️ RAG found no information, asking permission to search web")
                self.user_session.waiting_for_search_permission = True
                self.user_session.pending_search_query = user_text
                # Add instruction to ask permission
                permission_note = "\n\nIMPORTANT: I don't have information about this in my current knowledge. You MUST politely say: 'I'm not sure about that specific detail. Would you like me to search online for more information?' Then WAIT for user permission before using search_web tool."
                if hasattr(turn_ctx, 'items') and len(turn_ctx.items) > 0:
                    for i, item in enumerate(turn_ctx.items):
                        if hasattr(item, 'role') and item.role == 'system':
                            from livekit.agents import llm as llm_mod
                            current_content = item.content[0] if isinstance(item.content, list) else item.content
                            new_system_msg = llm_mod.ChatMessage(
                                id=item.id,
                                role='system',
                                content=[current_content + permission_note]
                            )
                            turn_ctx.items[i] = new_system_msg
                            break
        else:
            # Non-banking question - allow automatic web search
            logger.info(f"💬 General question detected (no RAG needed): {user_text[:50]}...")
            # Set web search as approved for general queries
            self.user_session.web_search_approved = True
            logger.info("✅ Auto-approved web search for general query")
        
        # Save user message to database (now enabled with user profiles)
        try:
            session_mgr = await get_session_manager()
            await session_mgr.add_message(
                self.user_session.session_id,
                role="user",
                content=user_text
            )
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")


async def get_agent_instructions(is_local_mode: bool = True) -> tuple[str, str]:
    """
    Get agent instructions from database.
    Falls back to prompt.py if database is unavailable.
    
    Returns: (instructions, initial_greeting)
    """
    try:
        db_pool = await get_db_pool()
        from database.repository import AgentInstructionRepository
        
        repo = AgentInstructionRepository(db_pool)
        instruction = await repo.get_active_instruction(is_local_mode)
        
        if instruction:
            logger.info(f"Loaded instructions from database: {instruction.name}")
            return instruction.instructions, instruction.initial_greeting
    except Exception as e:
        logger.warning(f"Failed to load instructions from database: {e}")
    
    # Fallback to prompt.py
    from prompt import AGENT_INSTRUCTIONS, AGENT_INSTRUCTIONS_LOCAL
    instructions = AGENT_INSTRUCTIONS_LOCAL if is_local_mode else AGENT_INSTRUCTIONS
    logger.info("Using fallback instructions from prompt.py")
    return instructions, None


async def setup_rag_service() -> RAGService:
    """Initialize RAG service with document indexing"""
    global _rag_service
    
    # Return cached service if already initialized
    if _rag_service is not None:
        logger.info("Returning cached RAG service")
        return _rag_service
    
    try:
        db_pool = await get_db_pool()
        
        # Set up embedding service - use Ollama by default for better accuracy
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "ollama")
        embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        logger.info(f"Setting up RAG with embedding provider: {embedding_provider}, model: {embedding_model}")
        
        embedding_service = EmbeddingService(
            provider=embedding_provider, 
            model=embedding_model,
            ollama_url=ollama_url
        )
        
        # Initialize embedding service
        await embedding_service.initialize()
        logger.info(f"Embedding service initialized: {embedding_provider}/{embedding_model} (dim={embedding_service.dimension})")
        
        # Set up RAG indexer
        docs_path = Path(__file__).parent / "docs"
        indexer = RAGIndexer(
            docs_path=str(docs_path),
            db_pool=db_pool,
            embedding_service=embedding_service,
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
        )
        
        # Index documents NOW (not in background) so they're ready before users connect
        logger.info(f"Indexing documents from {docs_path}...")
        await indexer.index_directory()
        logger.info("Document indexing complete!")
        
        # Start directory watcher (optional)
        if os.getenv("RAG_WATCH_DIRECTORY", "false").lower() == "true":
            asyncio.create_task(indexer.watch_directory(interval=60))
        
        _rag_service = RAGService(indexer)
        logger.info(f"RAG service initialized, docs path: {docs_path}")
        return _rag_service
        
    except Exception as e:
        logger.error(f"Failed to setup RAG service: {e}")
        return None


# ============================================
# TTS TEXT PREPROCESSING
# ============================================

def preprocess_text_for_tts(text: str) -> str:
    """
    Preprocess text before sending to TTS to improve pronunciation.
    - USSD -> U S S D (individual letters)
    - *236# -> star 2 3 6 hash (phonetic)
    """
    import re
    
    # Replace *236# with phonetic version
    # Match *236# or *236 (with or without hash)
    text = re.sub(r'\*236#?', 'star 2 3 6 hash', text, flags=re.IGNORECASE)
    
    # Replace USSD with spaced letters (case insensitive)
    text = re.sub(r'\bUSSD\b', 'U S S D', text, flags=re.IGNORECASE)
    
    return text


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the voice agent.
    Creates isolated session for each user with database-backed configuration.
    """
    # Ensure services are initialized (happens once per worker)
    await ensure_services_initialized()
    
    await ctx.connect()
    
    logger.info(f"New connection - Room: {ctx.room.name}, Participant: {ctx.room.local_participant.identity}")
    
    # Get configuration
    use_online = os.getenv("USE_ONLINE_MODEL", "false").lower() == "true"
    is_local_mode = not use_online
    llm_provider_env = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Determine LLM provider
    if llm_provider_env == "vllm":
        llm_provider = LLMProviderType.VLLM
    elif llm_provider_env == "openrouter":
        llm_provider = LLMProviderType.OPENROUTER
    elif llm_provider_env == "google":
        if GOOGLE_AVAILABLE:
            llm_provider = LLMProviderType.GOOGLE
        else:
            logger.warning("Google plugin not available, falling back to Ollama")
            llm_provider = LLMProviderType.OLLAMA
    elif llm_provider_env == "google_realtime":
        if GOOGLE_AVAILABLE:
            llm_provider = LLMProviderType.GOOGLE_REALTIME
        else:
            logger.warning("Google plugin not available, falling back to Ollama")
            llm_provider = LLMProviderType.OLLAMA
    else:
        llm_provider = LLMProviderType.OLLAMA
    
    # Initialize session manager and create user session
    try:
        session_manager = await get_session_manager()
        user_session = await session_manager.create_session(
            room_id=ctx.room.name,
            participant_id=ctx.room.local_participant.identity,
            llm_provider=llm_provider,
            is_local_mode=is_local_mode
        )
        logger.info(f"Created session: {user_session.session_id}")
        
        # Add vision capabilities to instructions if using Google Realtime
        if llm_provider == LLMProviderType.GOOGLE_REALTIME:
            vision_instructions = """

VISION CAPABILITIES:
You can see the user through their camera and see their screen when shared.
- If user shares their screen, describe what you see and help them with their task
- If user turns on camera, you can see them and respond to visual cues
- When asked about something on screen, look at the screen share and describe it
- Be helpful with visual tasks: reading documents, analyzing images, navigating websites
- If you notice the user seems confused or struggling, offer helpful observations
"""
            user_session.instructions += vision_instructions
            logger.info("Added vision capabilities to instructions (Google Realtime)")
            
    except Exception as e:
        logger.error(f"Failed to create session from database: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to simple session with basic instructions
        fallback_instructions = """You are Batsi, a helpful voice assistant for TN CyberTech Bank.

COMMUNICATION STYLE:
- Be natural, conversational, and professional
- Keep responses concise (1-2 sentences for simple questions)
- Use human language: "Based on my understanding", "From what I know", "As far as I'm aware"
- Never mention "knowledge base", "database", or technical systems
- Speak as if you're a knowledgeable person helping a friend

YOUR CAPABILITIES:
You have access to these resources to help users:
1. Banking Knowledge Base - Comprehensive information about TN CyberTech Bank products, services, and policies
2. send_email - Send emails to users
3. search_web - Search the internet for general information

AVAILABLE TOOLS & WHEN TO USE THEM:

1. BANKING KNOWLEDGE (Your Primary Source):
   For ALL banking questions (accounts, services, fees, hours, products):
   - ALWAYS answer from the information you have FIRST
   - Be confident and helpful with your banking knowledge
   - Use natural phrases like "From what I know" or "Based on my understanding"
   
   ⚠️ IMPORTANT: If you DON'T have the banking information:
   - Admit you don't have that specific information
   - Say: "I don't have that information in my knowledge. Would you like me to search the internet for it?"
   - Only search if user approves

2. WEB SEARCH (search_web) - FALLBACK ONLY:
   Use ONLY when:
   - User asks about NON-banking topics (recipes, weather, news, travel, health)
   - You DON'T have the answer in your banking knowledge AND user approves search
   - User explicitly asks to "search the internet" or "look it up online"
   
   ❌ NEVER:
   - Combine web results with banking knowledge
   - Search for banking info if you already have the answer
   - Use web search as your first choice for banking questions
   
   ✅ CORRECT PATTERN:
   Banking question → Answer from knowledge OR admit you don't know
   General question → Use search_web automatically

3. EMAIL (send_email) - STRICT CONFIRMATION REQUIRED:
   ⚠️ CRITICAL: You MUST follow this EXACT process. No shortcuts!
   
   MANDATORY STEPS (DO ALL 4):
   Step 1: ASK - "What is your email address?"
   Step 2: WAIT - Let the user speak their email
   Step 3: CONFIRM - "Just to confirm, you said [email they said]. Is that correct?"
   Step 4: ONLY after they confirm YES, then call send_email
   
   ⚠️ If the email sounds garbled, unclear, or unusual:
   - Say "I didn't catch that clearly. Could you spell out your email address?"
   - Wait for them to spell it: "J-O-H-N at gmail dot com"
   - Then confirm: "So that's john@gmail.com, correct?"
   
   CORRECT EXAMPLE:
   User: "Send me an email with the summary"
   You: "Sure! What's your email address?"
   User: "john at gmail dot com"
   You: "Just to confirm, that's john@gmail.com - is that correct?"
   User: "Yes"
   You: "Great, what should the subject line be?"
   User: "Meeting Summary"
   You: "And what would you like the email to say?"
   User: "Summarize our conversation"
   NOW call: send_email(to_email="john@gmail.com", subject="Meeting Summary", body="...")
   
   ❌ NEVER DO THIS:
   - send_email(to_email="your email address", ...)
   - send_email(to_email="[email]", ...)
   - send_email(to_email="", ...)
   - send_email(to_email="bn/auser@...", ...) ← This is GARBLED, ask again!
   - Calling the tool before asking AND confirming the email
   - Guessing what the email address might be
   - Using an email that sounds wrong or garbled

EXAMPLES:
- "How do I open an account?" → Answer from your banking knowledge
- "What's your interest rate?" → Answer from your banking knowledge
- "Find me a chicken recipe" → Use search_web automatically (non-banking)
- "What's the weather today?" → Use search_web automatically (non-banking)
- "How do I get a loan at another bank?" → "I don't have information about other banks. Would you like me to search online?"
- "Tell me about your savings accounts" → Answer from your banking knowledge
"""
        
        # Add vision capabilities to instructions if using Google Realtime
        if llm_provider == LLMProviderType.GOOGLE_REALTIME:
            vision_instructions = """

VISION CAPABILITIES:
You can see the user through their camera and see their screen when shared.
- If user shares their screen, describe what you see and help them with their task
- If user turns on camera, you can see them and respond to visual cues
- When asked about something on screen, look at the screen share and describe it
- Be helpful with visual tasks: reading documents, analyzing images, navigating websites
- If you notice the user seems confused or struggling, offer helpful observations
"""
            fallback_instructions += vision_instructions
        
        user_session = UserSession(
            session_id=str(ctx.room.name),
            room_id=ctx.room.name,
            participant_id=ctx.room.local_participant.identity,
            instructions=fallback_instructions,
            initial_greeting="Hello! I'm Batsi from TN CyberTech Bank. How can I help you today?",
            llm_provider=llm_provider
        )
    
    # Use pre-initialized RAG service from prewarm
    global _rag_service
    rag_service = _rag_service
    if rag_service:
        logger.info("Using pre-initialized RAG service")
    else:
        logger.warning("RAG service not available (not initialized at startup)")
    
    # Get LLM configuration from provider manager
    use_google_realtime = False
    try:
        llm_manager = await get_llm_provider_manager()
        llm_config = llm_manager.get_openai_compatible_config(user_session.llm_provider)
        llm_base_url = llm_config["base_url"]
        llm_model = llm_config["model"]
        llm_api_key = llm_config["api_key"]
        llm_timeout = llm_config["timeout"]
        
        # Check if using Google Realtime (speech-to-speech)
        if user_session.llm_provider == LLMProviderType.GOOGLE_REALTIME:
            use_google_realtime = True
        
        logger.info(f"Using LLM provider: {user_session.llm_provider.value} - {llm_model}")
    except Exception as e:
        logger.warning(f"Failed to get LLM config from manager: {e}")
        # Fallback to environment variables
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if not ollama_url.endswith("/v1"):
            ollama_url = f"{ollama_url}/v1"
        llm_base_url = ollama_url
        llm_model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
        llm_api_key = "not-needed"
        llm_timeout = 120
    
    # STT Configuration
    stt_url = os.getenv("SPEACHES_STT_URL", "http://localhost:8000/v1")
    stt_model = os.getenv("SPEACHES_STT_MODEL", "Systran/faster-whisper-base.en")
    
    # TTS Configuration
    tts_url = os.getenv("SPEACHES_TTS_URL", "http://localhost:8000/v1")
    tts_model = os.getenv("SPEACHES_TTS_MODEL", "speaches-ai/Kokoro-82M-v1.0-ONNX")
    tts_voice = os.getenv("SPEACHES_TTS_VOICE", "af_heart")
    
    # Create STT (not needed for Google Realtime mode)
    stt = None
    if not use_google_realtime:
        stt = openai.STT(
            base_url=stt_url,
            model=stt_model,
            api_key="not-needed",
            language="en"
        )
    
    # Create LLM based on provider
    llm = None
    if use_google_realtime and GOOGLE_AVAILABLE:
        # Google Realtime API - speech-to-speech model
        google_realtime_model = os.getenv("GOOGLE_REALTIME_MODEL", "gemini-2.0-flash-live-001")
        google_realtime_voice = os.getenv("GOOGLE_REALTIME_VOICE", "Puck")
        llm = google.realtime.RealtimeModel(
            model=google_realtime_model,
            voice=google_realtime_voice,
        )
        logger.info(f"Using Google Realtime API: {google_realtime_model} (voice: {google_realtime_voice})")
    elif user_session.llm_provider == LLMProviderType.GOOGLE and GOOGLE_AVAILABLE:
        # Standard Google Gemini LLM
        llm = google.LLM(
            model=llm_model,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )
        logger.info(f"Using Google Gemini LLM: {llm_model}")
    else:
        # OpenAI-compatible LLM (Ollama, vLLM, OpenRouter)
        llm = openai.LLM(
            base_url=llm_base_url,
            model=llm_model,
            timeout=llm_timeout,
            api_key=llm_api_key,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )
    
    # Create TTS (not needed for Google Realtime mode which has built-in TTS)
    tts = None
    if not use_google_realtime:
        base_tts = openai.TTS(
            base_url=tts_url,
            model=tts_model,
            voice=tts_voice,
            api_key="not-needed"
        )
        
        # Wrap TTS to preprocess text before synthesis
        class PreprocessingTTS:
            """TTS wrapper that preprocesses text for better pronunciation"""
            def __init__(self, base_tts):
                self._base_tts = base_tts
                
            def synthesize(self, text: str, **kwargs):
                """Preprocess and synthesize"""
                processed_text = preprocess_text_for_tts(text)
                if processed_text != text:
                    logger.info(f"TTS preprocessing: '{text[:50]}...' -> '{processed_text[:50]}...'")
                return self._base_tts.synthesize(processed_text, **kwargs)
            
            def __getattr__(self, name):
                """Delegate all other attributes to base TTS"""
                return getattr(self._base_tts, name)
        
        tts = PreprocessingTTS(base_tts)
    
    # Load VAD with optimized settings
    vad = silero.VAD.load(
        min_speech_duration=float(os.getenv("VAD_MIN_SPEECH", "0.15")),
        min_silence_duration=float(os.getenv("VAD_MIN_SILENCE", "0.9")),
        prefix_padding_duration=float(os.getenv("VAD_PREFIX_PADDING", "0.5")),
        max_buffered_speech=float(os.getenv("VAD_MAX_BUFFERED", "60.0")),
        activation_threshold=float(os.getenv("VAD_ACTIVATION_THRESHOLD", "0.45")),
    )
    
    # Create agent with session context
    agent = VoiceAgent(user_session)
    if rag_service:
        agent.set_rag_service(rag_service)
        logger.info("✓ RAG service attached to agent (will augment on user speech)")
    
    # Create session with explicit tools list
    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        tools=AGENT_TOOLS,  # Explicitly pass tools like agent_old.py
        allow_interruptions=True,
    )
    
    # Add callback to save assistant responses to database
    original_after_llm_cb = session.after_llm_cb if hasattr(session, 'after_llm_cb') else None
    
    # Save assistant responses (now enabled with user profiles)
    async def save_assistant_response(agent_instance, chat_ctx):
        """Save assistant response to database"""
        try:
            # Get the latest assistant message
            messages = chat_ctx.messages if hasattr(chat_ctx, 'messages') else []
            assistant_messages = [msg for msg in messages if hasattr(msg, 'role') and msg.role == 'assistant']
            
            if assistant_messages:
                latest_message = assistant_messages[-1]
                assistant_text = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
                
                # Save to database
                try:
                    session_mgr = await get_session_manager()
                    await session_mgr.add_message(
                        user_session.session_id,
                        role="assistant",
                        content=assistant_text
                    )
                    logger.debug(f"Saved assistant message: {assistant_text[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to save assistant message: {e}")
            
            # Call original callback if it exists
            if original_after_llm_cb:
                await original_after_llm_cb(agent_instance, chat_ctx)
                
        except Exception as e:
            logger.warning(f"Error in save response callback: {e}")
    
    session.after_llm_cb = save_assistant_response
    logger.info("Message saving enabled (anonymous profile tracking)")
    
    # Handle session end with conversation summarization
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        async def end_session_async():
            try:
                session_manager = await get_session_manager()
                # End session with summary generation enabled
                await session_manager.end_session_by_room(ctx.room.name, generate_summary=True)
                logger.info(f"✓ Participant disconnected, session ended with summary for room: {ctx.room.name}")
            except Exception as e:
                logger.error(f"Error ending session: {e}")
        
        asyncio.create_task(end_session_async())
    
    # Start the session with video input enabled for Google Realtime
    if use_google_realtime:
        # Google Realtime supports live video input from camera and screen share
        logger.info("Starting session with video input enabled (Google Realtime)")
        await session.start(
            room=ctx.room,
            agent=agent,
            room_options=room_io.RoomOptions(
                video_input=True,  # Enable video/screen share input for Gemini vision
            ),
        )
    else:
        # Standard STT-LLM-TTS pipeline without video
        await session.start(
            room=ctx.room,
            agent=agent,
        )
    
    logger.info(f"Agent session started for room: {ctx.room.name}")
    
    # Agent initiates conversation with greeting from database
    if user_session.initial_greeting:
        logger.info(f"Agent speaking initial greeting: {user_session.initial_greeting[:50]}...")
        
        # For Google Realtime API, use generate_reply instead of say
        # because it handles speech natively without separate TTS
        if use_google_realtime:
            await session.generate_reply(
                instructions=f"Greet the user with exactly this message: {user_session.initial_greeting}"
            )
        else:
            await session.say(user_session.initial_greeting, allow_interruptions=True)
        
        # Save greeting to conversation history
        try:
            session_mgr = await get_session_manager()
            await session_mgr.add_message(
                user_session.session_id,
                role="assistant",
                content=user_session.initial_greeting
            )
        except Exception as e:
            logger.warning(f"Failed to save initial greeting to database: {e}")
    else:
        logger.warning("No initial greeting configured - agent will wait for user to speak first")


if __name__ == "__main__":
    # Configure worker for concurrent users
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        job_memory_warn_mb=int(os.getenv("WORKER_MEMORY_WARN_MB", "1500")),
        num_idle_processes=int(os.getenv("WORKER_IDLE_PROCESSES", "3")),
    )
    
    cli.run_app(worker_options)
