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
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero

load_dotenv()

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.INFO)

# Import our custom modules
from session_manager import get_session_manager, UserSession
from providers import get_llm_provider_manager, LLMProviderType
from database import get_db_pool
from database.rag import RAGIndexer, RAGService, EmbeddingService


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
    
    async def _augment_chat_context(self, turn_ctx, user_message: str):
        """
        Augment the chat context with RAG context based on user message.
        
        IMPORTANT: We modify turn_ctx directly because that's what LiveKit uses
        for the LLM generation. Just calling update_instructions() is NOT enough!
        """
        if self.rag_service:
            try:
                logger.info(f"🔍 Searching RAG for query: '{user_message}'")
                augmented = await self.rag_service.augment_prompt(
                    user_query=user_message,
                    base_instructions=self.base_instructions
                )
                
                # Log whether context was added
                if len(augmented) > len(self.base_instructions):
                    context_added = len(augmented) - len(self.base_instructions)
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
        
        # Augment chat context with RAG context BEFORE LLM processes
        # PASS turn_ctx so we can modify it directly!
        if user_text:
            await self._augment_chat_context(turn_ctx, user_text)
        
        # Save user message to database
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
    except Exception as e:
        logger.error(f"Failed to create session from database: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to simple session with basic instructions
        fallback_instructions = """You are Batsi, a friendly voice assistant for TN CyberTech Bank.

STYLE:
- Be conversational and friendly
- Give SHORT responses (1-2 sentences)

BANKING TRANSACTIONS (REQUIRE LOGIN):
When user wants to: check balance, make transfer, get statement, cardless withdrawal or bank balance or account info
→ Ask for username and PIN, then call authenticate_bank(username, password)

GENERAL CHAT (NO LOGIN NEEDED):
When user is: chatting, asking questions, wanting information
→ Just respond naturally or use search_web"""
        
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
    try:
        llm_manager = await get_llm_provider_manager()
        llm_config = llm_manager.get_openai_compatible_config(user_session.llm_provider)
        llm_base_url = llm_config["base_url"]
        llm_model = llm_config["model"]
        llm_api_key = llm_config["api_key"]
        llm_timeout = llm_config["timeout"]
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
    
    # Create STT
    stt = openai.STT(
        base_url=stt_url,
        model=stt_model,
        api_key="not-needed",
        language="en"
    )
    
    # Create LLM
    llm = openai.LLM(
        base_url=llm_base_url,
        model=llm_model,
        timeout=llm_timeout,
        api_key=llm_api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    
    # Create TTS
    tts = openai.TTS(
        base_url=tts_url,
        model=tts_model,
        voice=tts_voice,
        api_key="not-needed"
    )
    
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
    
    # Create session
    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        allow_interruptions=True,
    )
    
    # Add callback to save assistant responses to database
    original_after_llm_cb = session.after_llm_cb if hasattr(session, 'after_llm_cb') else None
    
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
    logger.info("Message saving callbacks enabled")
    
    # Handle session end (must be synchronous, use create_task for async work)
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        async def end_session_async():
            try:
                session_manager = await get_session_manager()
                await session_manager.end_session_by_room(ctx.room.name)
                logger.info(f"Participant disconnected, session ended for room: {ctx.room.name}")
            except Exception as e:
                logger.error(f"Error ending session: {e}")
        
        asyncio.create_task(end_session_async())
    
    # Start the session
    await session.start(
        room=ctx.room,
        agent=agent,
    )
    
    logger.info(f"Agent session started for room: {ctx.room.name}")
    
    # Agent initiates conversation with greeting from database
    if user_session.initial_greeting:
        logger.info(f"Agent speaking initial greeting: {user_session.initial_greeting[:50]}...")
        await session.say(user_session.initial_greeting, allow_interruptions=True)
        
        # Save the greeting as first assistant message in conversation history
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
