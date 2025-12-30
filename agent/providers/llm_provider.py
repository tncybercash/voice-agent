"""
LLM Provider Manager for vLLM, Ollama, and OpenRouter.
Supports concurrent requests with connection pooling and load balancing.
"""
import os
import logging
import asyncio
import random
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger("llm_provider")


class LLMProviderType(str, Enum):
    """Supported LLM providers"""
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENROUTER = "openrouter"
    GOOGLE = "google"
    GOOGLE_REALTIME = "google_realtime"


@dataclass
class LLMConfig:
    """Configuration for an LLM provider"""
    provider: LLMProviderType
    base_url: str
    model: str
    api_key: Optional[str] = None
    timeout: int = 120
    max_tokens: int = 2048
    temperature: float = 0.7
    max_concurrent: int = 10  # Max concurrent requests per provider


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                limit=self.config.max_concurrent,
                limit_per_host=self.config.max_concurrent,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a chat completion"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy"""
        pass
    
    def get_openai_compatible_url(self) -> str:
        """Get the OpenAI-compatible base URL"""
        return self.config.base_url


class OllamaProvider(LLMProvider):
    """Ollama LLM provider"""
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        async with self._semaphore:
            session = await self.get_session()
            
            url = f"{self.config.base_url}/v1/chat/completions"
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "stream": kwargs.get("stream", False),
            }
            
            headers = {"Content-Type": "application/json"}
            
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Ollama error: {error}")
                return await resp.json()
    
    async def health_check(self) -> bool:
        try:
            session = await self.get_session()
            url = f"{self.config.base_url}/api/tags"
            async with session.get(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    def get_openai_compatible_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if not base.endswith("/v1"):
            return f"{base}/v1"
        return base


class VLLMProvider(LLMProvider):
    """vLLM LLM provider - optimized for high-throughput inference"""
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        async with self._semaphore:
            session = await self.get_session()
            
            url = f"{self.config.base_url}/v1/chat/completions"
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "stream": kwargs.get("stream", False),
            }
            
            headers = {
                "Content-Type": "application/json",
            }
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"vLLM error: {error}")
                return await resp.json()
    
    async def health_check(self) -> bool:
        try:
            session = await self.get_session()
            url = f"{self.config.base_url}/health"
            async with session.get(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"vLLM health check failed: {e}")
            return False


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider - cloud API with many models"""
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        async with self._semaphore:
            session = await self.get_session()
            
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "HTTP-Referer": "https://voice-agent.local",
                "X-Title": "Voice Agent"
            }
            
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"OpenRouter error: {error}")
                return await resp.json()
    
    async def health_check(self) -> bool:
        try:
            session = await self.get_session()
            url = "https://openrouter.ai/api/v1/models"
            headers = {"Authorization": f"Bearer {self.config.api_key}"}
            async with session.get(url, headers=headers) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {e}")
            return False


class GoogleProvider(LLMProvider):
    """Google Gemini LLM provider - standard chat completions"""
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        # Google uses a different API format than OpenAI
        # This provider is mainly for config storage - actual calls use livekit plugin
        async with self._semaphore:
            # Return empty - the actual LLM is created via livekit plugin in agent.py
            return {"message": "Use livekit google plugin directly"}
    
    async def health_check(self) -> bool:
        # Just check if API key is set
        return bool(self.config.api_key)
    
    def get_openai_compatible_url(self) -> str:
        # Google doesn't use OpenAI-compatible URL, return marker
        return "google://gemini"


class GoogleRealtimeProvider(LLMProvider):
    """Google Gemini Live API provider - realtime speech-to-speech"""
    
    def __init__(self, config: LLMConfig, voice: str = "Puck"):
        super().__init__(config)
        self.voice = voice
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        # Realtime API doesn't use standard chat completions
        async with self._semaphore:
            return {"message": "Use livekit google realtime plugin directly"}
    
    async def health_check(self) -> bool:
        return bool(self.config.api_key)
    
    def get_openai_compatible_url(self) -> str:
        return "google://realtime"


class LLMProviderManager:
    """
    Manages multiple LLM providers with automatic failover and load balancing.
    Optimized for 20+ concurrent users.
    """
    
    def __init__(self):
        self._providers: Dict[LLMProviderType, LLMProvider] = {}
        self._primary_provider: Optional[LLMProviderType] = None
        self._fallback_order: List[LLMProviderType] = []
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize providers from environment variables"""
        if self._initialized:
            return
        
        # Get primary provider from env
        primary = os.getenv("LLM_PROVIDER", "ollama").lower()
        
        # Initialize Ollama if configured
        ollama_url = os.getenv("OLLAMA_BASE_URL")
        ollama_model = os.getenv("OLLAMA_MODEL")
        if ollama_url and ollama_model:
            self._providers[LLMProviderType.OLLAMA] = OllamaProvider(LLMConfig(
                provider=LLMProviderType.OLLAMA,
                base_url=ollama_url,
                model=ollama_model,
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "20")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            ))
            logger.info(f"Initialized Ollama provider: {ollama_url} / {ollama_model}")
        
        # Initialize vLLM if configured
        vllm_url = os.getenv("VLLM_BASE_URL")
        vllm_model = os.getenv("VLLM_MODEL")
        if vllm_url and vllm_model:
            self._providers[LLMProviderType.VLLM] = VLLMProvider(LLMConfig(
                provider=LLMProviderType.VLLM,
                base_url=vllm_url,
                model=vllm_model,
                api_key=os.getenv("VLLM_API_KEY"),
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "20")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            ))
            logger.info(f"Initialized vLLM provider: {vllm_url} / {vllm_model}")
        
        # Initialize OpenRouter if configured
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL")
        if openrouter_key and openrouter_model:
            self._providers[LLMProviderType.OPENROUTER] = OpenRouterProvider(LLMConfig(
                provider=LLMProviderType.OPENROUTER,
                base_url="https://openrouter.ai/api/v1",
                model=openrouter_model,
                api_key=openrouter_key,
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "20")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            ))
            logger.info(f"Initialized OpenRouter provider: {openrouter_model}")
        
        # Initialize Google if configured (for standard Gemini LLM)
        google_key = os.getenv("GOOGLE_API_KEY")
        google_model = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
        if google_key:
            # Store config for Google - actual plugin will be created in agent.py
            self._providers[LLMProviderType.GOOGLE] = GoogleProvider(LLMConfig(
                provider=LLMProviderType.GOOGLE,
                base_url="https://generativelanguage.googleapis.com",
                model=google_model,
                api_key=google_key,
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "20")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            ))
            logger.info(f"Initialized Google provider: {google_model}")
            
            # Also register for Google Realtime
            google_realtime_model = os.getenv("GOOGLE_REALTIME_MODEL", "gemini-2.0-flash-live-001")
            google_realtime_voice = os.getenv("GOOGLE_REALTIME_VOICE", "Puck")
            self._providers[LLMProviderType.GOOGLE_REALTIME] = GoogleRealtimeProvider(LLMConfig(
                provider=LLMProviderType.GOOGLE_REALTIME,
                base_url="https://generativelanguage.googleapis.com",
                model=google_realtime_model,
                api_key=google_key,
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "20")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            ), voice=google_realtime_voice)
            logger.info(f"Initialized Google Realtime provider: {google_realtime_model} (voice: {google_realtime_voice})")
        
        # Set primary provider
        if primary == "vllm" and LLMProviderType.VLLM in self._providers:
            self._primary_provider = LLMProviderType.VLLM
        elif primary == "openrouter" and LLMProviderType.OPENROUTER in self._providers:
            self._primary_provider = LLMProviderType.OPENROUTER
        elif primary == "google" and LLMProviderType.GOOGLE in self._providers:
            self._primary_provider = LLMProviderType.GOOGLE
        elif primary == "google_realtime" and LLMProviderType.GOOGLE_REALTIME in self._providers:
            self._primary_provider = LLMProviderType.GOOGLE_REALTIME
        elif LLMProviderType.OLLAMA in self._providers:
            self._primary_provider = LLMProviderType.OLLAMA
        elif self._providers:
            self._primary_provider = list(self._providers.keys())[0]
        
        # Set fallback order
        self._fallback_order = [p for p in self._providers.keys() if p != self._primary_provider]
        
        self._initialized = True
        logger.info(f"LLM Provider Manager initialized. Primary: {self._primary_provider}, Fallbacks: {self._fallback_order}")
    
    def get_provider(self, provider_type: LLMProviderType = None) -> Optional[LLMProvider]:
        """Get a specific provider or the primary one"""
        if provider_type:
            return self._providers.get(provider_type)
        return self._providers.get(self._primary_provider)
    
    def get_openai_compatible_config(self, provider_type: LLMProviderType = None) -> Dict[str, str]:
        """Get OpenAI-compatible configuration for a provider"""
        provider = self.get_provider(provider_type)
        if not provider:
            raise ValueError(f"Provider not found: {provider_type or self._primary_provider}")
        
        return {
            "base_url": provider.get_openai_compatible_url(),
            "model": provider.config.model,
            "api_key": provider.config.api_key or "not-needed",
            "timeout": provider.config.timeout,
        }
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        provider_type: LLMProviderType = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion with automatic failover.
        Tries primary provider first, then fallbacks.
        """
        await self.initialize()
        
        providers_to_try = []
        if provider_type and provider_type in self._providers:
            providers_to_try.append(provider_type)
        else:
            if self._primary_provider:
                providers_to_try.append(self._primary_provider)
            providers_to_try.extend(self._fallback_order)
        
        last_error = None
        for ptype in providers_to_try:
            provider = self._providers.get(ptype)
            if not provider:
                continue
            
            try:
                logger.debug(f"Trying LLM provider: {ptype.value}")
                result = await provider.chat_completion(messages, **kwargs)
                return result
            except Exception as e:
                logger.warning(f"Provider {ptype.value} failed: {e}")
                last_error = e
                continue
        
        raise Exception(f"All LLM providers failed. Last error: {last_error}")
    
    async def health_check_all(self) -> Dict[LLMProviderType, bool]:
        """Check health of all providers"""
        results = {}
        for ptype, provider in self._providers.items():
            results[ptype] = await provider.health_check()
        return results
    
    async def close(self):
        """Close all provider sessions"""
        for provider in self._providers.values():
            await provider.close()


# Singleton instance
_provider_manager: Optional[LLMProviderManager] = None
_manager_lock = asyncio.Lock()


async def get_llm_provider_manager() -> LLMProviderManager:
    """Get or create the global LLM provider manager"""
    global _provider_manager
    
    async with _manager_lock:
        if _provider_manager is None:
            _provider_manager = LLMProviderManager()
            await _provider_manager.initialize()
        return _provider_manager
