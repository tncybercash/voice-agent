import logging
import os
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero

load_dotenv()

logger = logging.getLogger("local-agent")
logger.setLevel(logging.INFO)

class LocalAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.
            Keep your responses natural and conversational for voice interaction."""
        )

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    # Get configuration from environment
    stt_url = os.getenv("SPEACHES_STT_URL")
    stt_model = os.getenv("SPEACHES_STT_MODEL")
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    ollama_model = os.getenv("OLLAMA_MODEL")
    tts_url = os.getenv("SPEACHES_TTS_URL")
    tts_model = os.getenv("SPEACHES_TTS_MODEL")
    tts_voice = os.getenv("SPEACHES_TTS_VOICE")
    
    # Ensure Ollama URL has /v1 for OpenAI compatibility
    if not ollama_url.endswith("/v1"):
        ollama_url = f"{ollama_url}/v1"
    
    # Create STT with language specified for better accuracy
    stt = openai.STT(base_url=stt_url, model=stt_model, api_key="not-needed", language="en")
    
    # Create LLM with very high timeout for Ollama (models can be slow on first request)
    llm = openai.LLM(base_url=ollama_url, model=ollama_model, timeout=120, api_key="not-needed", temperature=0.7)
    
    # Create TTS
    tts = openai.TTS(base_url=tts_url, model=tts_model, voice=tts_voice, api_key="not-needed")
    
    # Load VAD with more sensitive settings for better voice pickup
    # Lower activation_threshold = more sensitive to voice (picks up quieter speech)
    # Shorter min_speech_duration = captures shorter utterances
    # Longer min_silence_duration = more patient with natural pauses
    vad = silero.VAD.load(
        min_speech_duration=0.15,     # Captures shorter speech segments
        min_silence_duration=0.9,     # Waits longer before considering speech ended (more natural)
        prefix_padding_duration=0.5,  # Captures beginning of speech properly (increased)
        max_buffered_speech=60.0,
        activation_threshold=0.45,    # Lower = more sensitive to voice (adjust 0.4-0.6 for balance)
    )
    
    # Create session with enhanced VAD and turn detection
    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        allow_interruptions=True,
    )
    
    await session.start(
        room=ctx.room,
        agent=LocalAgent(),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, job_memory_warn_mb=1500))