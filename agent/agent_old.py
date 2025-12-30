import os
import logging
import httpx
import sys
import subprocess
import time
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip
from livekit.plugins import noise_cancellation, silero
from livekit.plugins import openai as openai_plugin
from livekit.plugins import google as google_plugin
from livekit.plugins import elevenlabs as elevenlabs_plugin
from prompt import AGENT_INSTRUCTIONS, AGENT_INSTRUCTIONS_LOCAL
from tools import (
    send_email, 
    search_web, 
    authenticate_bank,
    select_user_profile,
    get_current_user_info,
    get_account_balance, 
    get_account_statement, 
    process_internal_transfer, 
    process_cardless_withdrawal,
    process_rtgs_transfer,
    unlock_account_send_otp,
    unlock_account_verify_otp,
    unlock_account_get_security_questions,
    unlock_account_answer_question,
    unlock_account_reset_pin
)

load_dotenv(".env.local")

logger = logging.getLogger(__name__)

USE_ONLINE_MODEL = os.getenv("USE_ONLINE_MODEL", "true").lower() == "true"
ONLINE_MODEL_PROVIDER = os.getenv("ONLINE_MODEL_PROVIDER", "google").lower()

# ...existing code for local/online model setup, speaches, ollama, etc...

def get_agent_instructions():
    if USE_ONLINE_MODEL:
        return AGENT_INSTRUCTIONS
    else:
        return AGENT_INSTRUCTIONS_LOCAL

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=get_agent_instructions())

AGENT_TOOLS = [
    authenticate_bank,
    select_user_profile,
    get_current_user_info,
    get_account_balance,
    get_account_statement,
    process_internal_transfer,
    process_rtgs_transfer,
    process_cardless_withdrawal,
    send_email,
    search_web,
    unlock_account_send_otp,
    unlock_account_verify_otp,
    unlock_account_get_security_questions,
    unlock_account_answer_question,
    unlock_account_reset_pin,
]

server = AgentServer()

@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    logger.info("Initialized fresh session userdata")
    session = None
    if USE_ONLINE_MODEL:
        llm = google_plugin.realtime.RealtimeModel(
            model=os.getenv("GOOGLE_REALTIME_MODEL", "gemini-2.0-flash-exp"),
            voice=os.getenv("GOOGLE_REALTIME_VOICE", "Aoede"),
        )
        session = AgentSession(
            llm=llm,
            tools=AGENT_TOOLS,
        )
    else:
        llm = openai_plugin.LLM(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        )
        session = AgentSession(
            llm=llm,
            tools=AGENT_TOOLS,
        )
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            ),
            video_input=True,
        ),
    )
    background_audio = BackgroundAudioPlayer(
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.1),
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.1),
        ]
    )
    await background_audio.start(room=ctx.room, agent_session=session)
    if USE_ONLINE_MODEL:
        await session.generate_reply(
            instructions="Greet the user warmly in English, introduce yourself as Batsi from TN CyberTech Bank support, then offer them the choice to continue in English, Shona, or Ndebele. Say something like: 'Hello! I'm Batsi from TN CyberTech Bank. I can assist you in English, Shona, or Ndebele. Which language would you prefer?'"
        )
    else:
        await session.say("Hello! I'm Batsi from TN CyberTech Bank. How can I help you today?")

if __name__ == "__main__":
    print("Starting TN CyberTech Bank AI Voice Agent...")
    print(f"Using {'online' if USE_ONLINE_MODEL else 'local'} model")
    if USE_ONLINE_MODEL:
        print(f"Online model provider: {ONLINE_MODEL_PROVIDER}")
    else:
        print("Local model: Ollama")
    print("Preloading VAD...")
    silero.VAD.load()
    agents.cli.run_app(server)
